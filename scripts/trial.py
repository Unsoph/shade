"""Run one experimental arm and log per-second telemetry to CSV (for E3/E9).

    python scripts/trial.py --arm shade --minutes 30 --source clip.mp4 \
        --out benchmarks/trials/shade-run1.csv
    python scripts/trial.py --arm static-0 --minutes 30 ...
    python scripts/trial.py --arm shade-forecast ...
    python scripts/trial.py --arm shade-gated ...

Arms: static-N (rung N fixed; firmware throttles on its own), shade (default
policy), shade-forecast (learned thermal advisor), shade-gated (gate+shift).
Record ambient temperature, case and cooling in the run notes yourself.
`--fake --simulate thermal_ramp --speed 30` exercises the script anywhere.
"""

import argparse
import csv
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.app import build_runtime, run  # noqa: E402
from src.core.config import load_config  # noqa: E402

FIELDS = ["t_s", "temp_c", "cpu_util", "fps", "rung", "state", "throttled",
          "detections", "mem_pct", "frames"]


def apply_arm(config: dict, arm: str) -> int:
    """Edit the config for the arm; returns the start rung."""
    if arm.startswith("static-"):
        k = int(arm.split("-")[1])
        config["policy"]["level_to_rung"] = [k] * 4  # never moves off rung k
        return k
    if arm == "shade-forecast":
        config["policy"]["forecast"]["enabled"] = True
    elif arm == "shade-gated":
        config["scheduling"].update(gate=True, shift=True)
    elif arm != "shade":
        raise SystemExit(f"unknown arm {arm!r}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arm", required=True)
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--source", default=None)
    ap.add_argument("--config", default="config/deployment.yaml")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--simulate", default=None)
    ap.add_argument("--speed", type=float, default=1.0)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)
    config = load_config(args.config)
    config["watchdog"]["state_path"] = ""  # trials must not touch real state
    if args.simulate:
        config["device"]["hardware"] = "simulated"
        config["simulation"] = {"scenario": args.simulate, "speed": args.speed}
    start = apply_arm(config, args.arm)
    rt = build_runtime(config, start, args.fake, db_path=args.out + ".db")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    f = open(args.out, "w", newline="")
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    t0, lock = time.monotonic(), threading.Lock()

    def log_row(snap):
        with lock:
            writer.writerow({
                "t_s": round(time.monotonic() - t0, 2), "temp_c": snap.cpu_temp,
                "cpu_util": round(snap.cpu_util, 3), "fps": round(snap.fps, 2),
                "rung": snap.rung, "state": snap.state,
                "throttled": int("Thermally throttled" in snap.throttle_status),
                "detections": snap.detections, "mem_pct": snap.memory_percent,
                "frames": snap.frame_count})
            f.flush()

    rt.health.add_listener(log_row)
    source = args.source if args.source is not None else config["camera"]["source"]
    stopper = threading.Timer(args.minutes * 60.0,
                              lambda: os.kill(os.getpid(), signal.SIGINT))
    stopper.daemon = True
    stopper.start()
    run(rt, source, display=False, max_frames=0)
    stopper.cancel()
    f.close()
    print(f"Wrote {args.out} and {args.out}.db")
    return 0


if __name__ == "__main__":
    sys.exit(main())
