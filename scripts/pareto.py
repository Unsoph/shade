"""Utility-vs-thermal-risk trade-off: sweep each policy's safety knob.

    python scripts/pareto.py --seeds 10

Reactive SHADE is swept by shifting all temperature thresholds by `delta`;
SHADE+forecast by its `target_c` (and optionally `--horizon`). Risk is the
share of time above 70 C and the share of time firmware-throttled. A policy
only "wins" where its points are up-and-left of the other's. SIMULATION ONLY.
"""

import argparse
import logging
import random
import statistics as st
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.defaults import DEFAULTS  # noqa: E402
from src.sim.loop import jitter, simulate  # noqa: E402
from src.sim.policies import Shade  # noqa: E402
from src.sim.profile import ASSUMED  # noqa: E402
from src.sim.scenarios import SCENARIOS, perturb  # noqa: E402

BANDS = ("warm_c", "degrade_c", "critical_c", "upgrade_gate_c")
REL = [p.util for p in ASSUMED]


def reactive(delta):
    over = {k: DEFAULTS["policy"][k] + delta for k in BANDS}
    return Shade(f"reactive d={delta:+.0f}", 4, REL, **over)


def forecast(target, horizon):
    fc = {**DEFAULTS["policy"]["forecast"], "target_c": target,
          "horizon_s": horizon}
    return Shade(f"forecast T={target:.0f} H={horizon:.0f}", 4, REL,
                 forecast=True, forecast_cfg=fc)


def points(scenario, make, knobs, seeds, duration, throttle_scale):
    out = []
    for knob in knobs:
        rs = []
        for seed in range(seeds):
            rng = random.Random(seed)
            cfg = replace(perturb(SCENARIOS[scenario], rng),
                          throttle_scale=throttle_scale)
            rs.append(simulate(make(knob), cfg, jitter(ASSUMED, rng),
                               duration, seed=seed))
        out.append((knob, *[st.mean(getattr(r, m) for r in rs) for m in
                            ("utility", "above_warm_pct", "throttled_pct",
                             "switches_per_h")]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--duration", type=float, default=3600.0)
    ap.add_argument("--throttle-scale", type=float, default=0.55)
    ap.add_argument("--horizon", type=float, default=1800.0)
    ap.add_argument("--only", default="")
    args = ap.parse_args(argv)
    logging.disable(logging.CRITICAL)
    for scen in ([args.only] if args.only else SCENARIOS):
        print(f"\n== {scen}  (throttle_scale={args.throttle_scale})")
        print(f"{'policy':26s} {'utility':>8s} {'>70C %':>8s} {'thrtl %':>8s} {'sw/h':>7s}")
        rows = points(scen, reactive, [-12, -8, -4, 0, 4], args.seeds,
                      args.duration, args.throttle_scale)
        rows += points(scen, lambda t: forecast(t, args.horizon),
                       [60, 64, 68, 72, 76], args.seeds, args.duration,
                       args.throttle_scale)
        names = [reactive(k).name for k, *_ in rows[:5]] + \
                [forecast(k, args.horizon).name for k, *_ in rows[5:]]
        for name, (_, u, w, t, s) in zip(names, rows):
            print(f"{name:26s} {u:8.2f} {w:8.1f} {t:8.1f} {s:7.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
