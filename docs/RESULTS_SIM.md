# RESULTS (simulation and offline) — read the caveats first

**Nothing here was measured on a Raspberry Pi.** Sections 1-2 come from a
closed-loop *model* of a device whose parameters are assumptions (`src/sim/`);
section 3 uses the real YOLOv8n model on a synthetic pan of one still image on
an x86 cloud machine. Raw outputs: `docs/results/`, `docs/gating_eval_output.txt`.
Reproduce: `python scripts/ablation.py`, `python scripts/pareto.py`,
`python scripts/eval_gating.py --image <photo>`.

## 1. Policy comparison on a simulated thermal plant

Setup: 4 rungs (assumed utilisation 0.95/0.50/0.28/0.15, detection rate
8/4/3.5/2 Hz, quality 1.0/1.0/0.85/0.70), first-order thermal plant plus
variants (second thermal mass, temperature-dependent leakage, ambient steps),
10 seeds with ±15 % parameter jitter, 1 h virtual time. "Utility" = detections
per second x quality. `scripts/ablation.py` prints the full table.

What the data supports:

1. **Letting the firmware throttle gave the highest *mean* utility** in all six
   scenarios (`static-0`, e.g. cool-room 7.43 vs 5.63 for SHADE), while being
   throttled 16-89 % of the time at the assumed 0.55 speed penalty. Its
   worst-5 % utility only falls below SHADE's when throttling is harsh:
   at `--throttle-scale 0.25`, 2.0 vs 3.8-4.0 in warm-room, hot-enclosure,
   ambient-step and leaky; at 0.55 it stays higher (4.4-5.5 vs 3.4-4.0).
   So SHADE's case rests on predictability and thermal margin, not
   throughput, and only if real throttling is costly. Experiment E3 decides.
2. **Guards help, but thresholds set the operating point.** Versus a plain
   two-threshold thermostat (10-seed means, switches/h and share of time above
   70 C): cool-room 60 -> 57 sw/h and 58 % -> 5 %; two-mass 32 -> 31 and
   38 % -> 3 %; ambient-step 61 -> 36 and 55 % -> 26 %; warm-room 47 -> 14 and
   41 % -> 21 %. In hot-enclosure (72 % -> 67 %) and leaky (66 % -> 49 %) SHADE
   still sits near 70 C most of the time because the *thresholds* allow it
   (see `pareto_*.txt` for shifting them). Removing the guards
   (`shade-noguards`) roughly doubled switching in cool-room (108 vs 57) and
   changed utility by under 4 %.
3. **Slope anticipation mattered in one of six scenarios.** `shade-noanticip`
   equals `shade-reactive` except in `leaky` (63 % vs 49 % of time above 70 C,
   27 vs 41 switches/h): there the heat-up accelerates with temperature.
   Elsewhere heat-up is slow relative to the 10 s slope window.
4. **The learned thermal-model advisor (`policy.forecast`) did not beat tuned
   reactive control.** It never throttled and rarely exceeded 70 C, but at equal
   thermal risk the reactive controller achieved higher utility
   (`docs/results/pareto_*.txt`: cool room, reactive shifted by -4 C: 5.03 at 0 %
   above 70 C vs forecast best 4.08-4.59 at 0-1 %). Reason: reactive control
   duty-cycles between rungs and exploits the chip's thermal mass, while the
   steady-state forecast settles on one sustainable rung. Its advantage is low
   switching (2-5/h vs 30-50/h) and an explicit uncertainty-aware margin.
   It stays off by default and is kept for the hardware study; a
   burst-aware (finite-budget) controller is the obvious next step.

Threats to validity: the plant, rung profiles and throttle penalty are
invented; the estimator is well-specified for the base plant (mismatch cases
are the two-mass and leaky scenarios); one plant family only.

## 2. What would make this a claim
Fit the plant to a Pi 5 (sustained benchmark logs temperature), replace the
profiles with `benchmark.py`/`eval_agreement.py` output, and re-run
section 1. Only then do the orderings above become findings about a device.

## 3. Content-gated detection and box shifting (real model, synthetic pan)
Reference = YOLOv8n on every frame (360 frames: static, slow pan 2 px/frame,
static, fast pan 8 px/frame). Arms replay the scheduler with the budget
"one detection per N frames". Calls = share of frames that ran the detector.

| N | arm | calls | F1 @IoU .5 | F1 @IoU .75 | F1 @.75, fast pan |
|---|-----|-------|-----------|-------------|-------------------|
| 4 | hold (today) | 0.25 | 0.979 | 0.933 | 0.808 |
| 4 | shift | 0.25 | 0.979 | 0.958 | 0.889 |
| 4 | gate | 0.19 | 0.979 | 0.933 | 0.808 |
| 4 | gate+shift | 0.19 | 0.979 | 0.958 | 0.889 |
| 8 | hold | 0.12 | 0.937 | 0.873 | 0.639 |
| 8 | shift | 0.12 | 0.957 | 0.931 | 0.811 |
| 8 | gate+shift | 0.09 | 0.956 | 0.928 | 0.811 |

- **Gating** removed ~25 % of detector calls with no F1 change here, because
  the first and third quarters of the clip are static. The saving is as large
  as the share of static time in real footage, so it must be measured per scene.
- **Shifting** recovers localisation on skipped frames (IoU .75, N=8, fast
  pan: 0.639 -> 0.811) at zero extra detector cost; at IoU .5 the gain is small.
- Limits: global pan of a still image (suits phase correlation); objects that
  move independently, deform or leave the frame are not covered; only
  detector-call counts were measured, not Pi latency or energy.
