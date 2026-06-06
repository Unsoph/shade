# CLAUDE.md — SHADE Project Context

## What is this project?

**SHADE** (Self-Healing Adaptive Deployment Engine) is an autonomous operations
agent for edge AI inference systems. It detects hardware-level degradation,
executes corrective model-switching and recovery actions, and maintains
structured audit trails of every decision.

**Primary target:** Raspberry Pi 5 (8GB), CPU-only inference.
**Future target:** NVIDIA Jetson Nano / Xavier NX / Orin.

## Current state: Stage 0 — Foundation (COMPLETE)

Live YOLOv8n ONNX inference on camera or video file with hardware-abstracted
backend pattern.

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

```
shade/
├── run.py                              # Entry point
├── config/deployment.yaml              # All runtime configuration
├── models/                             # ONNX model files (gitignored)
├── scripts/
│   ├── setup.py                        # Diagnostic checks
│   └── test_smoke.py                   # Headless inference smoke test
├── requirements.txt
├── src/
│   ├── inference/
│   │   ├── detection.py                # Detection dataclass
│   │   ├── postprocess.py             # Letterbox, NMS, COCO labels
│   │   ├── backend_factory.py          # Factory — only import point
│   │   └── backends/
│   │       ├── base_backend.py         # ABC contract
│   │       ├── onnx_backend.py         # Working: Pi CPU inference
│   │       ├── tflite_backend.py       # Stub
│   │       ├── openvino_backend.py     # Stub
│   │       └── tensorrt_backend.py     # Stub (Jetson only)
│   └── video/
│       ├── pipeline.py                 # Capture loop, FPS
│       └── draw.py                     # Bounding box rendering
├── docs/
│   ├── PROJECT_STATE.md                # Detailed current state
│   └── NEXT_STEPS.md                   # What to build next
└── CLAUDE.md                           # This file
```

## Staged build plan (8 stages)

| Stage | Name                      | Status      |
|-------|---------------------------|-------------|
| 0     | Foundation                | ✅ COMPLETE  |
| 1     | Health Monitoring         | ⬜ NEXT      |
| 2     | Decision Engine           | ⬜ Planned   |
| 3     | Adaptive Model Switching  | ⬜ Planned   |
| 4     | Watchdog Recovery         | ⬜ Planned   |
| 5     | Edge Hardware Optimization| ⬜ Planned   |
| 6     | Observability             | ⬜ Planned   |
| 7     | Production Hardening      | ⬜ Planned   |

## Key constraints

- Every stage ends in a runnable, committable system.
- No file > 150 lines.
- No code for future stages in the current stage.
- Prefer working demo on Pi over elegant incomplete code.
- A stable 8 FPS demo on Pi beats an imaginary 60 FPS Jetson project.
- Threading for CPU-bound work, asyncio for I/O-bound.
- On Pi: always check vcgencmd availability before using it, psutil fallback.

## Model ladder (Pi 5)

| Tier | Model              | Expected FPS | Use when              |
|------|--------------------|--------------|----------------------|
| 3    | yolov8s FP32       | 2–5          | NOMINAL, cool, stable |
| 2    | yolov8n FP32       | 5–9          | NOMINAL, moderate     |
| 1    | yolov8n INT8       | 8–12         | DEGRADED              |
| 0    | NanoDet-Plus       | 4–8          | CRITICAL / emergency  |

Downgrade: 3→2→1→0. Upgrade: 0→1→2→3 (thermal-gated).

## How to run

```bash
cd /Users/shreyassharma/Work/shade
pip install -r requirements.txt
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
