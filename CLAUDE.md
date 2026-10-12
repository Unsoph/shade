# CLAUDE.md — SHADE Project Context

## What is this project?

**SHADE** (Self-Healing Adaptive Deployment Engine) is an autonomous operations
agent for edge AI inference systems. It detects hardware-level degradation,
executes corrective model-switching and recovery actions, and maintains
structured audit trails of every decision.

**Primary target:** Raspberry Pi 5 (8GB), CPU-only inference.
**Future target:** NVIDIA Jetson Nano / Xavier NX / Orin.

## Current state: Stages 0-7 implemented (simulation-verified, not yet Pi-measured)

Detection, health monitoring, decision engine, ladder with background hot-swap,
watchdog, benchmarking/quantization tools, observability server, chaos runs and
CI are in place. The open work is hardware measurement (docs/EXPERIMENTS.md) and
threshold tuning. See README.md for the verified / not-verified table.

## Architecture decisions

- **Backend abstraction:** All inference goes through `InferenceBackend` ABC →
  `BackendFactory`. No direct backend imports outside `backends/`.
- **Hardware target:** Pi 5 first. Jetson stubs exist but raise `NotImplementedError`.
- **Runtime:** ONNX Runtime CPU (`onnxruntime`, not `onnxruntime-gpu`).
  TFLite, OpenVINO, and TensorRT are stubs for future stages.
- **Camera:** OpenCV VideoCapture with auto-detect for USB vs Pi Camera (picamera2).
- **Config-driven:** All settings in `config/deployment.yaml`. No magic numbers in code.
- **150-line file limit:** No file exceeds 150 lines. Split before that limit.

## Project structure

See README.md "Layout". Key entry points: `run.py`, `src/app.py`
(`build_runtime`, `run`), `src/core/decision/engine.py`, `src/core/model_manager.py`,
`src/watchdog/supervisor.py`, `src/observability/server.py`.

## Build stages

All of 0-7 are done: Foundation, Health Monitoring, Decision Engine, Adaptive
Model Switching, Watchdog Recovery, Edge Optimization (tools), Observability,
Production Hardening. Next: run the experiments on a Pi 5 and tune.

## Key constraints

- Every stage ends in a runnable, committable system.
- No file > 150 lines.
- Prefer working demo on Pi over elegant incomplete code.
- A stable 8 FPS demo on Pi beats an imaginary 60 FPS Jetson project.
- Threading for CPU-bound work, asyncio for I/O-bound.
- On Pi: always check vcgencmd availability before using it, psutil fallback.

## Model ladder

Configured in `ladder:` (config/deployment.yaml); rungs with missing model files
are skipped. Default: yolov8n 640 -> 640 frame-skip -> 320 frame-skip -> 320 INT8.
Expected FPS is unmeasured; do not write numbers until E1 in EXPERIMENTS.md is run.
Upgrade gate is 65 C (configurable). NanoDet was dropped.

## How to run

```bash
cd /Users/shreyassharma/Work/shade
pip install -r requirements-dev.txt
# Download model:
# wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.onnx -P models/
python run.py --source 0              # USB camera
python run.py --source video.mp4      # Video file
python run.py --headless              # No display window
python scripts/setup.py               # Diagnostic checks only
```

## Dependencies

- Python 3.10+
- onnxruntime >= 1.17.0
- opencv-python-headless >= 4.8.0
- numpy, pyyaml, psutil

## Testing

`python -m pytest` (2 tests need models/yolov8n.onnx + tests/fixtures/bus.jpg or
SHADE_TEST_IMAGE), `python scripts/check_line_limit.py`, `python scripts/chaos.py`.
Tests must never write to the real logs/ directory.
