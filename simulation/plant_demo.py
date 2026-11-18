"""Thermal plant demo: one vs two thermal masses under a load step.

    python simulation/plant_demo.py [--minutes 30] [--out simulation/figures/plant_demo.png]

Parameters are the PlantConfig assumptions, not fitted to a Pi yet.
"""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.sim.plant import PlantConfig, ThermalPlant  # noqa: E402


def run(cfg, load, minutes, dt=1.0, seed=1):
    plant = ThermalPlant(cfg, seed=seed)
    t = np.arange(0.0, minutes * 60.0, dt)
    temp, throttled, speed = [], [], []
    for ti in t:
        measured, scale = plant.step(load(ti), dt, ti)
        temp.append(measured)
        throttled.append(plant.throttled)
        speed.append(scale)
    return t, np.array(temp), np.array(throttled), np.array(speed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--out", default=str(ROOT / "simulation/figures/plant_demo.png"))
    args = ap.parse_args(argv)

    def load(t):
        return 0.35 if t < 300 else 1.0  # light load, then full load at 5 min

    cfgs = {"one mass": PlantConfig(),
            "two masses": PlantConfig(slow_frac=0.4, tau_slow_s=600)}
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.5, 5), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1.2]})
    for (name, cfg), color in zip(cfgs.items(), ("tab:blue", "tab:orange")):
        t, temp, thr, speed = run(cfg, load, args.minutes)
        a1.plot(t / 60, temp, lw=1, color=color, label=name)
        a1.fill_between(t / 60, 20, 90, where=thr, color=color, alpha=0.12)
        a2.step(t / 60, speed, where="post", color=color, lw=1.2)
    a1.axhline(80, color="crimson", ls="--", lw=0.8)
    a1.axhline(77, color="crimson", ls=":", lw=0.8)
    a1.text(0.3, 80.8, "throttle on (80 C)", color="crimson", fontsize=8)
    a1.text(0.3, 74.2, "off (77 C)", color="crimson", fontsize=8)
    a1.set_ylim(25, 88)
    a1.set_ylabel("CPU temperature (C)")
    a1.legend(frameon=False, loc="lower right")
    a1.set_title("Simulated plant, load step at 5 min (assumed parameters)",
                 fontsize=10)
    a2.set_ylabel("speed x")
    a2.set_xlabel("time (min)")
    a2.set_ylim(0.4, 1.1)
    fig.tight_layout()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
