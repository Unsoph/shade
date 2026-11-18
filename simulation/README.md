# simulation/

Workspace for SHADE's simulation work: the checklist of what to model,
the extra libraries, runnable scripts, and their outputs.

Reusable model code (plant, policies, loop, scenarios) lives in `src/sim/`
so tests and the paper pipeline can import it. This folder holds the
scripts that drive it and the files they produce.

## Layout

| Path | What |
|---|---|
| `ASPECTS.md` | Everything to simulate, with status (have / partial / to build / needs Pi data) |
| `requirements.txt` | Simulation and figure libraries (not needed on the Pi) |
| `plant_demo.py` | Thermal plant demo: one vs two thermal masses, throttle relay |
| `amr_twin.py` | AMR digital twin (PyBullet) with SHADE onboard; single run or `--compare` |
| `amr_plots.py` | Figures for the AMR twin (traces, comparison, camera montage) |
| `figures/` | Generated plots (git-ignored) |
| `results/` | Generated CSV/JSON from runs (git-ignored) |

## Setup

```bash
cd shade
python3 -m venv .venv && source .venv/bin/activate
pip install -r simulation/requirements.txt
```

## Run

```bash
python simulation/plant_demo.py      # -> simulation/figures/plant_demo.png
```

## AMR digital twin

A 24 V differential-drive AMR (about 22 kg) drives a warehouse loop in
PyBullet and parks at two stations. A Raspberry Pi 5 on board runs SHADE:

```
route -> wheels (PyBullet physics) -> onboard camera frames (rendered)
      -> SHADE Scheduler (content gate) -> CPU load -> Pi temperature
      -> HealthSnapshot -> DecisionEngine -> ladder rung -> CPU load ...
motors + Pi + electronics -> battery (voltage sag, undervoltage flag)
```

Code: `src/sim/amr/` (params, robot, world, camera, nav, compute, battery,
twin). Overrides: `config/amr_twin.yaml`. Tests: `tests/test_amr_*.py`.

```bash
python simulation/amr_twin.py                         # SHADE + gate, 15 min
python simulation/amr_twin.py --compare --minutes 15  # 4 policies
python simulation/amr_twin.py --gui --minutes 3       # watch it (desktop)
```

Modelled: rigid-body drive with torque limits, rolling resistance, camera
view of shelves and walkers, content gate on rendered frames, CPU budget
and dropped detections, throttling, model-swap preload cost, battery sag
and undervoltage. Not modelled: localisation error, obstacle avoidance,
real detector output (rendered shapes are not COCO objects), fan.

PyBullet builds from source on some Python versions (about 4 minutes). If
it fails on Python 3.14, make the venv with Python 3.12
(`brew install python@3.12`).

All plant parameters are assumptions until fitted to a real Pi 5 trace
(experiment E6 in docs/EXPERIMENTS.md). Label every simulated result as
simulated.

## Library decisions

Use: numpy, scipy, matplotlib, joblib (and pytest for tests).
AMR twin: pybullet (3D rigid-body physics and the onboard camera).
Add for the paper only: schemdraw (RC schematic).
Defer: simpy (only for frame-queue latency claims).
Skip: pandas, seaborn, casadi (4 rungs -> exhaustive horizon search is
exact), filterpy (a short numpy Kalman filter instead), HotSpot, gem5.
