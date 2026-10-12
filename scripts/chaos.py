"""Fault-injection runs on the simulated machine (fake backends, no hardware).

    python scripts/chaos.py                    # all scenarios, 25x speed
    python scripts/chaos.py --only thermal_spike --speed 50

For each scenario it reports, in scenario time: how long after the fault
began SHADE first acted (detect), how long after the fault ended it was
back on rung 0 (recover), the deepest rung reached, the longest gap
between frames while swapping (stall) and the number of decisions.
A negative detect time means SHADE acted before the fault threshold (slope
anticipation). Timing is accurate to roughly +-1 s of scenario time.
These measure the control logic against scripted traces, not real silicon.
"""

import argparse
import copy
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.app import build_runtime, run  # noqa: E402
from src.core.defaults import DEFAULTS  # noqa: E402
from src.core.hardware.scenarios import get_scenario  # noqa: E402

LADDER = [
    {"name": f"r{i}", "model": f"fake-{s}", "input_size": s, "detect_every": e,
     "backend": "fake", "options": {"latency_ms": 2, "load_ms": 50}}
    for i, (s, e) in enumerate([(640, 1), (640, 2), (320, 2), (320, 3)])
]
SCENARIOS = ["thermal_spike", "thermal_ramp", "undervoltage", "memory_pressure"]
HORIZON_S = 420.0  # scenario seconds simulated per run


def is_fault(sample, policy) -> bool:
    return (sample.temp >= policy["degrade_c"] or sample.flags.undervoltage
            or sample.flags.throttled or sample.mem >= policy["mem_crit_pct"]
            or sample.swap >= policy["swap_warn_pct"])


def fault_window(name, policy):
    fn, onset, end = get_scenario(name), None, None
    for i in range(int(HORIZON_S * 2)):
        t = i / 2.0
        bad = is_fault(fn(t), policy)
        if bad and onset is None:
            onset = t
        if onset is not None and not bad and end is None:
            end = t
    return onset, end


def run_scenario(name: str, speed: float) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    cfg["device"]["hardware"] = "simulated"
    cfg["simulation"] = {"scenario": name, "speed": speed}
    cfg["ladder"] = LADDER
    cfg["ladder_settings"]["warmup"] = False
    cfg["watchdog"]["state_path"] = ""
    fps = 100.0
    max_frames = int(HORIZON_S / speed * fps)
    t0 = time.time()
    rt = build_runtime(cfg, db_path=":memory:")
    stamps, orig = [], rt.health.fps_tracker.tick
    rt.health.fps_tracker.tick = lambda: (stamps.append(time.monotonic()), orig())
    frames = run(rt, f"synthetic:160x120@{fps:g}", False, max_frames, close=False)
    events = list(reversed(rt.log.recent(1000, kind="decision")))
    onset, end = fault_window(name, DEFAULTS["policy"])
    at = lambda e: (e["ts"] - t0) * speed  # noqa: E731 - scenario seconds
    acts = [e for e in events if e["action"] in ("degrade", "upgrade")]
    downs = [e for e in acts if e["action"] == "degrade"]
    ups = [e for e in acts if e["action"] == "upgrade"]
    gaps = [(b - a) * 1000 for a, b in zip(stamps, stamps[1:])]
    out = {
        "scenario": name, "frames": frames, "decisions": len(acts),
        "detect_s": round(at(downs[0]) - onset, 1) if downs and onset else None,
        "deepest_rung": max((e["to_rung"] for e in downs), default=0),
        "recover_s": round(at(ups[-1]) - end, 1)
        if ups and end and ups[-1]["to_rung"] == 0 else None,
        "max_gap_ms": round(max(gaps), 1) if gaps else None,
    }
    rt.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", default="")
    ap.add_argument("--speed", type=float, default=25.0)
    args = ap.parse_args(argv)
    names = [args.only] if args.only else SCENARIOS
    cols = ["scenario", "frames", "decisions", "detect_s", "deepest_rung",
            "recover_s", "max_gap_ms"]
    print(" ".join(f"{c:>15s}" for c in cols))
    results = [run_scenario(n, args.speed) for n in names]
    for r in results:
        print(" ".join(f"{str(r[c]):>15s}" for c in cols))
    ok = all(r["deepest_rung"] > 0 and r["recover_s"] is not None for r in results)
    print("PASS: degraded and fully recovered in every scenario" if ok
          else "FAIL: a scenario did not degrade or did not recover")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
