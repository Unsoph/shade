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

All plant parameters are assumptions until fitted to a real Pi 5 trace
(experiment E6 in docs/EXPERIMENTS.md). Label every simulated result as
simulated.

## Library decisions

Use: numpy, scipy, matplotlib, joblib (and pytest for tests).
Add for the paper only: schemdraw (RC schematic).
Defer: simpy (only for frame-queue latency claims).
Skip: pandas, seaborn, casadi (4 rungs -> exhaustive horizon search is
exact), filterpy (a short numpy Kalman filter instead), HotSpot, gem5.
