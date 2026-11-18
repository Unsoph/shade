"""Run the AMR digital twin with SHADE onboard.

    python simulation/amr_twin.py                        # SHADE, gate on, 15 min
    python simulation/amr_twin.py --policy static-0      # no adaptation
    python simulation/amr_twin.py --compare --minutes 20 # policies side by side
    python simulation/amr_twin.py --gui --minutes 3      # watch it in PyBullet

Writes CSV traces, figures and a camera montage to simulation/results/.
All parameters are assumptions (src/sim/amr/params.py); results are
simulated and must be labelled as such.
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]

from amr_plots import compare_figure, montage, trace_figure  # noqa: E402
from src.sim.amr.params import load_amr_config  # noqa: E402
from src.sim.amr.twin import AmrTwin  # noqa: E402
from src.sim.policies import Shade, Static, Thermostat  # noqa: E402

N_RUNGS = 4
COMPARE = [("static-0", False), ("static-0", True), ("thermostat", True),
           ("shade", False), ("shade", True)]


def make_policy(name: str, cfg: dict):
    if name.startswith("static-"):
        return Static(int(name.split("-")[1]))
    if name == "thermostat":
        return Thermostat(N_RUNGS)
    costs = cfg["compute"]["det_cost_s"]
    return Shade("shade", N_RUNGS, [c / max(costs) for c in costs], **cfg["policy"])


def summarise(label: str, rows: list[dict], twin: AmrTwin) -> dict:
    n = len(rows)
    dist = sum(r["speed"] for r in rows)
    return {
        "run": label,
        "det_per_s": round(sum(r["detections"] for r in rows) / n, 2),
        "dropped_pct": round(100 * sum(r["dropped"] for r in rows)
                             / max(1, sum(r["wanted"] for r in rows)), 1),
        "throttled_pct": round(100 * sum(r["throttled"] for r in rows) / n, 1),
        "above_70c_pct": round(100 * sum(r["temp_c"] >= 70 for r in rows) / n, 1),
        "max_temp_c": round(max(r["temp_c"] for r in rows), 1),
        "switches_per_h": round(twin.switches * 3600 / n, 1),
        "model_swaps": twin.swaps,
        "energy_wh": round(twin.battery.energy_used_wh, 2),
        "pi_energy_wh": round(sum(r["pi_w"] for r in rows) / 3600, 2),
        "distance_m": round(dist, 1),
        "laps": rows[-1]["laps"],
    }


def run_one(cfg, policy_name, gate, minutes, out: Path, n_frames=0):
    cfg = dict(cfg, scheduling=dict(cfg["scheduling"], gate=gate))
    label = f"{policy_name}{'+gate' if gate else ''}"
    twin = AmrTwin(cfg, make_policy(policy_name, cfg))
    duration = minutes * 60
    picks = {round(duration * (i + 0.5) / n_frames, 1) for i in range(n_frames)}
    frames = []

    def grab(t, frame, ran):
        if round(t, 1) in picks:
            frames.append((f"t={t:.0f}s rung={twin.rung} det={'Y' if ran else 'n'}", frame))
    try:
        rows = twin.run(duration, grab if n_frames else None)
    finally:
        twin.close()
    with open(out / f"amr_{label}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    trace_figure(rows, cfg, out / f"amr_{label}.png", f"AMR twin: {label}")
    if frames:
        montage(frames, out / f"amr_{label}_camera.png")
    return label, rows, summarise(label, rows, twin)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="", help="YAML overrides (config/amr_twin.yaml)")
    ap.add_argument("--policy", default="shade",
                    help="shade | thermostat | static-0 .. static-3")
    ap.add_argument("--no-gate", action="store_true", help="disable content gate")
    ap.add_argument("--minutes", type=float, default=None)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--gui", action="store_true")
    ap.add_argument("--ambient", type=float, default=None,
                    help="override electronics-bay air temperature (C)")
    ap.add_argument("--frames", type=int, default=6, help="camera frames to save")
    ap.add_argument("--out", default=str(ROOT / "simulation" / "results"))
    args = ap.parse_args(argv)

    cfg = load_amr_config(args.config or None)
    cfg["sim"]["gui"] = args.gui
    if args.ambient is not None:
        cfg["plant"]["ambient_c"] = args.ambient
    minutes = args.minutes or cfg["sim"]["duration_s"] / 60
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = COMPARE if args.compare else [(args.policy, not args.no_gate)]
    runs, summary = {}, []
    for name, gate in plan:
        label, rows, s = run_one(cfg, name, gate, minutes, out, args.frames)
        runs[label] = rows
        summary.append(s)
        print("  ".join(f"{k}={v}" for k, v in s.items()), flush=True)
    if len(runs) > 1:
        compare_figure(runs, out / "amr_compare.png")
        with open(out / "amr_compare.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(summary[0]))
            w.writeheader()
            w.writerows(summary)
    print(f"results in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
