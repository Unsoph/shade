"""Closed-loop policy comparison on simulated thermal plants (virtual time).

    python scripts/ablation.py                  # all scenarios, 10 seeds
    python scripts/ablation.py --seeds 30 --duration 7200 --throttle-scale 0.3

SIMULATION ONLY: plant and rung profiles are assumptions (src/sim). The
output shows how the policies behave on a *model* of a device, which is how
the algorithm is debugged and ablated; it says nothing about a real Pi until
the plant is fitted to measurements (docs/EXPERIMENTS.md).
"""

import argparse
import csv
import logging
import random
import statistics as st
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.sim.loop import jitter, simulate  # noqa: E402
from src.sim.policies import make_policies  # noqa: E402
from src.sim.profile import ASSUMED  # noqa: E402
from src.sim.scenarios import SCENARIOS, perturb  # noqa: E402

METRICS = ["utility", "p5_utility", "throttled_pct", "above_warm_pct",
           "switches_per_h", "max_temp"]


def oracle_rung(cfg, profiles, duration, seed):
    """Best fixed rung in hindsight."""
    from src.sim.policies import Static
    best = max(range(len(profiles)), key=lambda r: simulate(
        Static(r), cfg, profiles, duration, seed=seed).utility)
    return best


def run(scenarios, seeds, duration, throttle_scale):
    rows = []
    rel = [p.util for p in ASSUMED]
    for name in scenarios:
        for seed in range(seeds):
            rng = random.Random(seed)
            cfg = replace(perturb(SCENARIOS[name], rng),
                          throttle_scale=throttle_scale)
            profiles = jitter(ASSUMED, rng)
            oracle = oracle_rung(cfg, profiles, duration, seed)
            for pol in make_policies(len(ASSUMED), rel, oracle):
                res = simulate(pol, cfg, profiles, duration, seed=seed)
                rows.append({"scenario": name, "policy": pol.name,
                             "seed": seed, **vars(res)})
    return rows


def summarize(rows):
    keys = sorted({(r["scenario"], r["policy"]) for r in rows},
                  key=lambda k: (list(SCENARIOS).index(k[0]), k[1]))
    out = []
    for scen, pol in keys:
        sel = [r for r in rows if r["scenario"] == scen and r["policy"] == pol]
        out.append({"scenario": scen, "policy": pol, **{
            m: (st.mean(r[m] for r in sel),
                st.pstdev(r[m] for r in sel)) for m in METRICS}})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--duration", type=float, default=3600.0)
    ap.add_argument("--throttle-scale", type=float, default=0.55,
                    help="speed/heat multiplier while firmware-throttled")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    logging.disable(logging.CRITICAL)
    names = [args.only] if args.only else list(SCENARIOS)
    rows = run(names, args.seeds, args.duration, args.throttle_scale)
    print(f"{'scenario':14s} {'policy':16s} " + " ".join(f"{m:>16s}" for m in METRICS))
    for s in summarize(rows):
        print(f"{s['scenario']:14s} {s['policy']:16s} " + " ".join(
            f"{s[m][0]:9.2f}±{s[m][1]:5.2f}" for m in METRICS))
    if args.out:
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
