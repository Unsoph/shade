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
| `amr_twin.py` | AMR digital twin (MuJoCo) with SHADE onboard; single run or `--compare` |
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

## AMR digital twin (MuJoCo)

A 24 V differential-drive AMR (about 22 kg plus a random payload) drives a
warehouse loop and parks at two stations. A Raspberry Pi 5 on board runs
SHADE:

```
route -> wheels (MuJoCo physics) -> onboard camera frames (rendered + noise)
      -> SHADE Scheduler (content gate) -> CPU load (+ random bursts)
      -> Pi temperature (drifting ambient) -> HealthSnapshot
      -> DecisionEngine -> ladder rung -> CPU load ...
motors + Pi + electronics -> battery (voltage sag, undervoltage flag)
```

Scene: 20 x 14 m hall, concrete floor with painted lanes, block walls,
pallet racking full of labelled cartons, pallet loads, packing table,
pillars, cones, parked forklift, and workers in hi-vis vests walking the
aisles. Textures are generated procedurally; no assets are downloaded.

Randomness (all from one seed, shared by every policy in `--compare`):
carton layout, worker paths/speed/pauses/clothing, station dwell times,
payload mass, wheel friction, ambient drift, background CPU bursts,
per-detection cost noise and camera pixel noise.

Code: `src/sim/amr/` (params, scene, mjcf_props, mjcf_robot, people,
textures, engine, disturb, nav, compute, battery, twin). Overrides:
`config/amr_twin.yaml`. Tests: `tests/test_amr_*.py`.

```bash
python simulation/amr_twin.py                         # SHADE + gate, 15 min
python simulation/amr_twin.py --compare --minutes 15  # 5 policies, same seed
python simulation/amr_twin.py --compare --ambient 45 --seed 3
```

Figures: raw per-second samples are drawn faintly with a rolling mean on
top (15 s in traces, 30 s in comparisons); rung and parked are steps.

Rendering: the small frames that feed SHADE's motion gate skip shadows and
reflections (about 5x faster on a CPU renderer; set
`render.gate_effects: true` on a GPU). Saved snapshots always use full
shadows and reflections. Headless Linux uses EGL; macOS uses native OpenGL.

Not modelled: localisation error, obstacle avoidance (workers pass through
the robot; they have no collision), real detector output (rendered
cartons and workers are not run through YOLO), fan.

All plant parameters are assumptions until fitted to a real Pi 5 trace
(experiment E6 in docs/EXPERIMENTS.md). Label every simulated result as
simulated.

## Library decisions

Use: numpy, scipy, matplotlib, joblib (and pytest for tests).
AMR twin: mujoco (rigid-body physics, rendering with shadows, onboard camera).
Add for the paper only: schemdraw (RC schematic).
Defer: simpy (only for frame-queue latency claims).
Skip: pandas, seaborn, casadi (4 rungs -> exhaustive horizon search is
exact), filterpy (a short numpy Kalman filter instead), HotSpot, gem5.
