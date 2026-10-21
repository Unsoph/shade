# PROJECT_STATE

**Stages 0-7 implemented.** 99 tests pass (2 more need a local model); CI runs
pytest, the 150-line check and a chaos scenario on Python 3.10-3.12.

## Done
- Detection, NMS, letterbox, ONNX + fake backends
- Health monitor, throttle parsing, simulated hardware scenarios
- Decision engine + SQLite audit log
- Ladder, ModelManager (background preload, atomic swap, failure fallback)
- Input health and camera reconnect
- Watchdog supervisor, heartbeat, last-known-good, sd_notify
- Benchmark / INT8 / export / agreement tools
- Observability server (/metrics, /status, /decisions, page)
- Chaos script, CI, Dockerfile (unbuilt), systemd unit

## Research layer (added after Stage 7)
- Motion gate + box shifting, forecast advisor (off), closed-loop simulator,
  ablation/Pareto scripts, Pareto ladder pruning; results in docs/RESULTS_SIM.md

## Not done / unknown
- No Pi 5 or Jetson run; thresholds untuned; no benchmark numbers
- 320 and INT8 models must be generated on a machine with ultralytics
- picamera2 path, Jetson/TFLite/OpenVINO/TensorRT backends
- Grafana dashboard
