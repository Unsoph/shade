"""Fit the simulator's thermal plant to a real trial and check fidelity (E7).

    python scripts/fit_plant.py paper/data/trials/shade-run1.csv \
        --out paper/data/e7_plant.json

Least-squares fit of dT/dt = (T_amb + k*u - T)/tau on a trial CSV (columns
temp_c, cpu_util, t_s; throttled samples excluded). Then replays static-0
and the default SHADE policy on the fitted plant and stores their simulated
metrics next to the fit quality (R^2 of the one-step prediction).
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.sim.loop import simulate  # noqa: E402
from src.sim.plant import PlantConfig  # noqa: E402
from src.sim.policies import Shade, Static  # noqa: E402
from src.sim.profile import ASSUMED  # noqa: E402


def fit(rows: list[dict], min_dt: float = 5.0):
    t = np.array([float(r["t_s"]) for r in rows])
    T = np.array([float(r["temp_c"]) for r in rows])
    u = np.array([float(r["cpu_util"]) for r in rows])
    ok = np.array([int(r["throttled"]) == 0 for r in rows])
    idx = [0]
    for i in range(1, len(t)):  # decimate to >= min_dt spacing
        if t[i] - t[idx[-1]] >= min_dt:
            idx.append(i)
    idx = np.array(idx)
    a, b = idx[:-1], idx[1:]
    keep = ok[a] & ok[b]
    a, b = a[keep], b[keep]
    dt = t[b] - t[a]
    y = (T[b] - T[a]) / dt
    uu = np.array([u[i:j + 1].mean() for i, j in zip(a, b)])
    X = np.column_stack([-T[a], np.ones(len(a)), uu])
    th, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ th
    r2 = 1 - ((y - pred) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-12)
    return {"tau_s": 1 / th[0], "ambient_c": th[1] / th[0], "k_c": th[2] / th[0],
            "r2_rate": float(r2), "n_pairs": int(len(y))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("trial_csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=float, default=1800.0)
    ap.add_argument("--seeds", type=int, default=10)
    args = ap.parse_args(argv)
    logging.disable(logging.CRITICAL)
    p = fit(list(csv.DictReader(open(args.trial_csv))))
    cfg = PlantConfig(ambient_c=p["ambient_c"], tau_s=p["tau_s"], k_c=p["k_c"])
    rel = [x.util for x in ASSUMED]
    sim = {}
    for key, make in (("static-0", lambda: Static(0)),
                      ("shade", lambda: Shade("shade", 4, rel))):
        rs = [simulate(make(), cfg, ASSUMED, args.duration, seed=s)
              for s in range(args.seeds)]
        sim[key] = {m: float(np.mean([getattr(r, m) for r in rs])) for m in
                    ("above_warm_pct", "throttled_pct", "max_temp")}
        sim[key]["above70_pct"] = sim[key].pop("above_warm_pct")
    Path(args.out).write_text(json.dumps({"fit": p, "sim": sim}, indent=2))
    print(json.dumps(p, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
