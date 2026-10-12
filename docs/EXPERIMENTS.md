# EXPERIMENTS — protocol for real measurements

No results exist yet. Fill the tables from `benchmarks/*.csv` and `logs/shade.db`;
do not copy numbers from elsewhere. Record: board, OS, cooling/case, ambient °C,
supply, commit hash, `onnxruntime` version.

## E1. Rung table (per rung, per thread count)
```
python scripts/benchmark.py --source <scene images> --threads 1,2,3,4 --frames 200
```
| rung | threads | p50 ms | p95 ms | p99 ms | eff FPS | RSS MB | agreement F1 |
|------|---------|--------|--------|--------|---------|--------|--------------|
| (empty) | | | | | | | |

Agreement: `python scripts/eval_agreement.py --images <scene images>` (or `--labels`).

## E2. Sustained drift
`python scripts/benchmark.py --sustained 600 --rungs nominal`: does p50 rise as
temperature climbs? Compare with and without a heatsink/fan.

## E3. Static vs adaptive under heat
Same video, enclosed case, ambient raised. Arms: static nominal, static emergency,
SHADE. Metrics: mean output FPS, FPS p5, time throttled, frames with detections,
rung changes. Repeat ≥ 5 times.

## E4. Swap cost
`swap_done` events: `swap_ms` (stall) and `first_frame_ms`, plus the longest frame
gap during a preload. Tune `preload_nice` / thread count if the gap exceeds budget.

## E5. Recovery
`kill -9` the engine and unplug the camera under `--supervised`; record time to
first frame after restart from `child_restart` / `camera_reconnect` events.

## E6. Threshold sensitivity
Vary `confirm_samples`, `dwell_s`, `upgrade_gate_c`; count rung changes per hour
(flapping) and time spent below nominal.
