# DESIGN

## Problem
Edge detectors fail quietly: a Pi 5 in a case soft-throttles near 80 °C, a weak
supply undervolts, memory fills, a camera freezes, a process hangs. A fixed model
either wastes headroom or collapses. SHADE adapts the workload *before* the
hardware forces it to, and keeps a record of why.

## Decision policy
1. **Signals** (`signals.py`): temperature, temperature slope over `slope_window_s`,
   throttle flags, RAM/swap, FPS (after `fps_grace_s` from a rung change), input fault.
2. **Pressure level 0-3** from bands (`warm_c`, `degrade_c`, `critical_c`, memory and
   swap bands). Slope ≥ `rise_c_per_s` while warm adds one level (anticipation).
3. **Target rung** = `level_to_rung[level]`.
4. **Guards**: moving down needs `confirm_samples` consecutive polls and `dwell_s`
   in the current rung; critical bypasses both. Moving up needs a calm window of
   `recover_hold_s`, temperature under `upgrade_gate_c`, no throttle flag, and
   only ever one rung at a time. `cooldown_s` follows every move.
5. **Failure handling**: a rung whose model cannot load (missing, too big for RAM
   headroom, load error) is marked unavailable and the engine falls back.

## Swapping
`ModelManager` loads the target model on a background thread (niceness
`preload_nice`, refuses below `min_free_mb_after_load` headroom), warms it, and
publishes it; the frame loop swaps the reference between frames via `poll()`.
Latest request wins. Rungs sharing a model (frame-skip) change parameters without
loading. The swap stall and first-frame time are logged per swap.

## Watchdog
Heartbeat written by the frame loop; a separate supervisor process restarts on
exit or silence, with exponential backoff, on the emergency rung (or the
last-known-good rung if recent). Crash loops end in `supervisor_gave_up`.

## Research layer
- **Scheduling** (`src/video/scheduler.py`, `propagate.py`): the ladder gives a
  detection budget (1 per `detect_every` frames). The gate stretches the interval
  while a 64x48 grey frame difference vs the anchor frame stays under
  `motion_threshold`; the shifter moves each box by the phase-correlation
  translation of its region. Neither can exceed the budget.
- **Forecast advisor** (`thermal_model.py`, `advisor.py`): fits
  dT/dt = (T_amb + k*u - T)/tau online (Bayesian RLS with a physics prior and
  forgetting; samples while firmware-throttled are excluded), calibrates per-rung
  utilisation from measurements, and returns the best rung whose forecast
  (upper confidence bound, `horizon_s` ahead) stays under `target_c`. The engine
  uses it as an extra floor on the target rung and as a model-based replacement
  for the fixed upgrade gate. Experimental, off, and not shown to help (RESULTS_SIM).
- **Simulator** (`src/sim`): first-order plant with optional second mass,
  leakage, ambient steps and throttling; policies drive the *real*
  `DecisionEngine` in virtual time.

## Related work
These informed the design and caveats; none is a claim about SHADE's results.
- DVFS on the Pi 5 (arXiv 2609.04705): INT8 was *slower* on their stack, hence
  "measure INT8 on the target" in this repo.
- Play It Cool (arXiv 2206.10849) and a thermal-throttling study (arXiv 2010.06291):
  sustained load throttles mobile/edge devices; motivates anticipation and sustained benchmarks.
- Adaptive edge AI position paper (arXiv 2604.07360): runtime adaptation as a
  systems problem.
- Accelerator forums (e.g. Hailo) report device failures that software must survive.

## Where SHADE is (and is not) distinctive
Individually, model switching, thermal-aware DVFS, and process supervision exist.
The contribution here is the combination in one small, readable, auditable
package for a commodity board: guarded one-step recovery, background hot-swap with
a measured stall, supervisor-driven emergency start, and a decision log with
reasons. It is not a new algorithm, and without hardware measurements it is not
yet shown to beat a static model. EXPERIMENTS.md defines how to show that.

## Known limitations
- Untuned thresholds; no Pi data. Preload competes for CPU on few-core machines.
- Single-process, single-camera, YOLOv8-family postprocessing only.
- HTTP endpoints are unauthenticated and read-only.
- Jetson/TFLite/OpenVINO/TensorRT backends are stubs.
