#!/usr/bin/env python3
"""Stage 2 demo: replay a hardware scenario through the decision engine.

No camera, model or sleeping: virtual time, one sample per second. Prints
each state/rung change with its reasons.

Usage: python scripts/demo_decisions.py [scenario] [--seconds N] [--db PATH]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import load_config
from src.core.decision.engine import DecisionEngine
from src.core.decision.log import DecisionLog
from src.core.hardware.scenarios import SCENARIOS, get_scenario
from src.core.snapshots import HealthSnapshot

RUNGS = 4


def to_snapshot(sample, t: float) -> HealthSnapshot:
    return HealthSnapshot(
        timestamp=t, cpu_temp=sample.temp, gpu_temp=sample.temp,
        memory_percent=sample.mem, swap_percent=sample.swap,
        throttle_status=sample.flags.human_readable,
        throttle_raw=sample.flags.raw_hex, fps=10.0,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("scenario", nargs="?", default="thermal_ramp",
                    choices=sorted(SCENARIOS))
    ap.add_argument("--seconds", type=int, default=420)
    ap.add_argument("--db", default=None, help="also write the audit log here")
    args = ap.parse_args()

    policy = load_config()["policy"]
    engine = DecisionEngine(policy, n_rungs=RUNGS)
    log = DecisionLog(args.db) if args.db else None
    scenario = get_scenario(args.scenario)

    print(f"{'t(s)':>5} {'temp':>6}  {'state':<14} {'rung':<9} reasons")
    for t in range(args.seconds):
        sample = scenario(float(t))
        d = engine.evaluate(to_snapshot(sample, float(t)))
        if d.notable:
            move = f"{d.prev_rung}->{d.rung}" if d.changed else f"{d.rung}"
            print(f"{t:>5} {sample.temp:>6.1f}  {d.state.value:<14} "
                  f"{move:<9} {'; '.join(d.reasons)}")
            if log:
                log.record_decision(d)
    print(f"\nfinal: rung {engine.rung}, state {engine.state.value}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:  # e.g. piped into head
        pass
