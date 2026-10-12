"""Benchmark every ladder rung (optionally x thread counts) and write a CSV.

    python scripts/benchmark.py --source models/../bus.jpg --frames 50
    python scripts/benchmark.py --fake --frames 20          # no models needed
    python scripts/benchmark.py --threads 1,2,4 --sustained 120

Numbers are only meaningful on the target device; this script records what
it measured and the host, it never fills in expected values.
"""

import argparse
import csv
import dataclasses
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bench.runner import bench_rung, frame_iter  # noqa: E402
from src.core.config import load_config, resolve_path  # noqa: E402
from src.core.ladder import parse_ladder  # noqa: E402
from src.core.simulation import FAKE_LADDER  # noqa: E402

FIELDS = ["host", "rung", "model", "input", "threads", "detect_every", "n",
          "mean_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms", "std_ms",
          "det_fps", "eff_fps", "rss_delta_mb", "temp_start_c", "temp_end_c"]


_MONITOR = []


def read_temp():
    """CPU temperature in C, or None when unavailable."""
    try:
        if not _MONITOR:
            from src.core.hardware.hw_factory import create_hw_monitor
            _MONITOR.append(create_hw_monitor({"device": {"hardware": "generic"}}))
        t = _MONITOR[0].get_cpu_temp()
        return round(t, 1) if t and t > 0 else None
    except Exception:
        return None


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--config", default="config/deployment.yaml")
    p.add_argument("--source", default="synthetic:640x480@0",
                   help="image, image folder, video, or synthetic:WxH@0")
    p.add_argument("--frames", type=int, default=50)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--threads", default="", help="comma list, e.g. 1,2,4")
    p.add_argument("--rungs", default="", help="comma list of rung names")
    p.add_argument("--sustained", type=float, default=0.0,
                   help="also run rung 0 repeatedly for N seconds; report drift")
    p.add_argument("--fake", action="store_true", help="use fake backends")
    p.add_argument("--out", default="", help="CSV path (default benchmarks/<host>-<ts>.csv)")
    return p.parse_args(argv)


def select_rungs(args, config):
    if args.fake:
        rungs = [r for r in parse_ladder({**config, "ladder": FAKE_LADDER})]
    else:
        from src.core.ladder import available_rungs
        rungs = available_rungs(parse_ladder(config))
    if args.rungs:
        names = set(args.rungs.split(","))
        rungs = [r for r in rungs if r.name in names]
    if args.threads:
        rungs = [dataclasses.replace(r, threads=int(t), name=f"{r.name}")
                 for r in rungs for t in args.threads.split(",")]
    return rungs


def sustained(rung, config, source, seconds, frames_per_window):
    """Repeat windows on one rung; thermal throttling shows up as p50 drift."""
    rows, end = [], time.monotonic() + seconds
    while time.monotonic() < end:
        t = read_temp()
        row = bench_rung(rung, config, frame_iter(source), frames_per_window, 1)
        rows.append({**row, "temp_start_c": t, "temp_end_c": read_temp()})
    return rows


def main(argv=None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    rungs = select_rungs(args, config)
    if not rungs:
        print("No runnable rungs (missing model files?). See scripts/export_models.py")
        return 1
    host = (platform.node() or "host") + ("-FAKE" if args.fake else "")
    rows = []
    for rung in rungs:
        t0 = read_temp()
        row = bench_rung(rung, config, frame_iter(args.source), args.frames, args.warmup)
        row.update(host=host, temp_start_c=t0, temp_end_c=read_temp())
        rows.append(row)
        print(f"{rung.name:12s} in={row['input']:4d} thr={row['threads']} "
              f"p50={row['p50_ms']:.1f}ms p95={row['p95_ms']:.1f}ms "
              f"det_fps={row['det_fps']:.1f} eff_fps={row['eff_fps']:.1f}")
    if args.sustained > 0:
        for row in sustained(rungs[0], config, args.source, args.sustained, args.frames):
            row.update(host=host)
            rows.append({**row, "rung": f"sustained:{row['rung']}"})
    out = Path(args.out) if args.out else resolve_path(
        f"benchmarks/{host}-{time.strftime('%Y%m%d-%H%M%S')}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
