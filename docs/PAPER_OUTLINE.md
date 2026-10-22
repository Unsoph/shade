> The actual draft now lives in `paper/` (LaTeX, generated tables, placeholders for every
> hardware result). Start with `paper/README.md`. This file is the original plan.

# Paper outline (working draft)

**Working title:** *Budgeted, auditable adaptation for edge detectors: a
degradation-ladder controller with content-aware scheduling.*
Venue tier is open: realistic targets are edge-AI/TinyML workshops or short
systems papers once the hardware experiments below exist.

## Claims we can currently defend (with a Pi run behind them: pending)
1. **Systems:** a small, open, fully tested control plane (guards, background
   hot-swap with measured stall, supervisor, audit log) for commodity boards.
2. **Evaluation method:** a closed-loop thermal simulator plus ablations for
   comparing adaptation policies reproducibly, and a protocol to fit it to a device.
3. **Scheduling:** content-gated detection plus ROI box shifting spends the
   ladder's detection budget more efficiently than blind frame skipping
   (offline result in docs/RESULTS_SIM.md section 3; needs real video).
4. **Honest negative result:** a learned thermal forecast did not beat
   tuned reactive control in simulation, and firmware throttling can out-score
   adaptation on mean throughput. Reporting *when adaptation pays* is itself a contribution.

## What is NOT claimed
Novel algorithm for DVFS/model switching; any Pi/Jetson numbers; accuracy of
the 320/INT8 rungs; superiority over existing systems.

## Sections
1. Introduction: failure modes of fixed-model edge deployments.
2. Related work (verify every citation against the paper itself before use):
   DVFS on Pi 5 (arXiv 2609.04705), Play It Cool (2206.10849), thermal
   throttling study (2010.06291), adaptive edge AI position (2604.07360);
   plus dynamic-inference / early-exit work, model-switching systems,
   frame-skipping/tracking-by-detection (e.g. SORT-style trackers, optical-flow
   propagation) and watchdog/self-healing literature still to be surveyed.
3. System design (docs/DESIGN.md).
4. Scheduling: gate + shift (method, cost).
5. Evaluation: E1-E9 in docs/EXPERIMENTS.md; plant fit; ablations.
6. Discussion: when adaptation pays (throttle penalty sweep), limits, ethics of safety claims.

## Minimum experiments before submission
E1 rung table, E2 sustained drift, E3 static vs adaptive (>= 5 runs, enclosed),
E7 plant fit + sim/real agreement, E8 gating on real video with ground truth,
E9 forecast vs reactive Pareto on the device. Add a second device if aiming higher.
