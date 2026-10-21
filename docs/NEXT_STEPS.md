# NEXT_STEPS

1. Run on a Pi 5: `scripts/setup.py`, then `run.py --source 0 --supervised --serve`.
2. Generate the 320 and INT8 models (README, "With a real model") and run
   EXPERIMENTS.md E1-E4. Record results in a table in that file.
3. Tune `policy` (bands, dwell, `upgrade_gate_c`) and `preload_nice` from E3/E4.
4. Decide on INT8 per measurement; adjust the ladder accordingly.
5. Run E7-E9 (EXPERIMENTS.md), then re-run scripts/ablation.py with the fitted plant.
6. Optional: Grafana dashboard over /metrics, TFLite/OpenVINO backend, Jetson monitor.
7. Build the Docker image on the target and fix what breaks.
