# AMR digital twin: first policy comparison (SIMULATED)

**Status: simulated, one seed, assumed parameters.** Nothing here is a
hardware measurement. Thermal, compute and power parameters are the
assumptions in `src/sim/amr/params.py` and `src/sim/plant.py`; they must be
replaced with Pi 5 measurements (E1, E2, E6) before any number is quoted in
the paper. With one seed there are no confidence intervals yet.

Setup: MuJoCo warehouse (20 x 14 m), 24 V differential-drive AMR driving a
loop for 15 simulated minutes (6 laps, 254 m) and parking 45 s (+/-40 %)
at two stations; 6 walking workers; seed 0, identical for every policy.
Ambient is the electronics-bay air temperature with a slow random drift.

Reproduce:

```bash
python simulation/amr_twin.py --compare --minutes 15 --out simulation/results/bay35
python simulation/amr_twin.py --compare --minutes 15 --ambient 45 --out simulation/results/bay45
```

## 35 C bay

| policy | det/s | dropped % | throttled % | time > 70 C % | max C | switches/h | model swaps |
|---|---|---|---|---|---|---|---|
| static 640 | 7.29 | 27.1 | 48.9 | 91.8 | 80.7 | 0 | 0 |
| static 640 + gate | 5.22 | 4.3 | 0.0 | 37.4 | 77.0 | 0 | 0 |
| thermostat + gate | 5.14 | 4.2 | 0.0 | 30.1 | 75.1 | 16 | 2 |
| SHADE | 5.41 | 0.4 | 0.0 | 34.3 | 72.8 | 4 | 0 |
| SHADE + gate | 4.50 | 4.0 | 0.0 | 4.4 | 71.6 | 40 | 0 |

## 45 C bay

| policy | det/s | dropped % | throttled % | time > 70 C % | max C | switches/h | model swaps |
|---|---|---|---|---|---|---|---|
| static 640 | 5.63 | 43.7 | 86.0 | 95.0 | 80.6 | 0 | 0 |
| static 640 + gate | 4.89 | 10.5 | 24.6 | 89.6 | 80.7 | 0 | 0 |
| thermostat + gate | 3.64 | 3.0 | 0.0 | 33.0 | 75.9 | 100 | 16 |
| SHADE | 5.25 | 0.4 | 0.0 | 44.0 | 76.0 | 32 | 7 |
| SHADE + gate | 3.12 | 0.5 | 0.0 | 15.1 | 72.5 | 12 | 0 |

## What the runs suggest (to be confirmed on hardware and over seeds)

1. Without adaptation the Pi throttles for half the run at 35 C and most of
   it at 45 C, and drops 27-44 % of the detections it attempts.
2. The content gate alone removes throttling at 35 C but not at 45 C.
3. SHADE alone avoided throttling in both bays with the fewest dropped
   detections (0.4 %) and the highest throughput of the non-throttling
   policies at 45 C. The thermostat also avoided throttling but flapped
   (100 switches/h, 16 model swaps at 45 C).
4. SHADE + gate ran coolest but delivered the fewest detections: the gate
   makes the load bursty (driving vs parked) and the engine reacts to the
   bursts. The two mechanisms are not additive as tuned; this interaction
   is the next thing to study.

## Caveats on the metric

Detections per second counts detector runs. The gate skips frames while the
scene is static, which loses little information, so det/s understates the
gated runs. A fairer metric is detection freshness while the scene is
changing (e.g. age of the latest detection during motion), which needs real
detections on rendered frames. That is not modelled yet.

Files: `bay35_compare.*`, `bay45_compare.*`, `bay35_shade_gate_trace.png`,
`bay45_shade_camera.jpg` (onboard and chase snapshots).
