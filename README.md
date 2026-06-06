<p align="center">
  <img src="https://img.shields.io/badge/Platform-Raspberry%20Pi%205-c51a4a?style=for-the-badge&logo=raspberrypi&logoColor=white" />
  <img src="https://img.shields.io/badge/Runtime-ONNX%20Runtime-007CFF?style=for-the-badge&logo=onnx&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Stage-0%20of%207-orange?style=for-the-badge" />
</p>

# SHADE — Self-Healing Adaptive Deployment Engine

> Autonomous operations agent for edge AI inference systems. Detects hardware-level
> degradation, executes corrective model-switching and recovery actions on constrained
> devices, and maintains structured audit trails of every decision.

**Prototype built on Raspberry Pi under constrained edge compute to validate
self-healing inference principles. Architecture is hardware-agnostic and designed
for direct migration to NVIDIA Jetson for autonomous systems deployment.**

---

## What SHADE Does

SHADE monitors an edge AI inference pipeline in real time and autonomously:

- **Detects** thermal throttling, memory pressure, FPS degradation, and power supply issues
- **Decides** when to downgrade or upgrade the active model using hysteresis and cooldown logic
- **Swaps** models atomically at frame boundaries without dropping frames
- **Recovers** from crashes via a watchdog process with exponential backoff
- **Logs** every decision to a structured audit trail (SQLite)

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      SHADE Engine                        │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   Video      │  │  Inference   │  │   Health       │  │
│  │   Pipeline   │──│  Backend     │──│   Monitor      │  │
│  │  (OpenCV)    │  │  (ONNX/TFL)  │  │  (Temp/FPS/    │  │
│  └─────────────┘  └──────────────┘  │   Memory)      │  │
│                          │          └────────────────┘  │
│                          │                   │          │
│                   ┌──────┴──────┐    ┌───────┴───────┐  │
│                   │  Hot-Swap   │    │   Decision    │  │
│                   │  Manager    │◄───│   Engine      │  │
│                   │ (atomic,    │    │  (state       │  │
│                   │  frame-     │    │   machine,    │  │
│                   │  boundary)  │    │   hysteresis) │  │
│                   └─────────────┘    └───────────────┘  │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Watchdog    │  │  Decision    │  │  Metrics       │  │
│  │  (separate   │  │  Log         │  │  Exporter      │  │
│  │   process)   │  │  (SQLite)    │  │  (Prometheus)  │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Model Ladder (Raspberry Pi 5)

| Tier | Model | Expected FPS | Trigger |
|------|-------|-------------|---------|
| 3 — Nominal | YOLOv8s FP32 | 2–5 | Temp < 55°C, no throttle |
| 2 — Standard | YOLOv8n FP32 | 5–9 | Moderate load |
| 1 — Degraded | YOLOv8n INT8 | 8–12 | Thermal/perf degraded |
| 0 — Emergency | NanoDet-Plus | 4–8 | Critical / crash recovery |

Downgrades are automatic under stress. Upgrades are **thermal-gated** — never
upgrade when CPU temp exceeds 55°C or throttle flags are non-zero.

## Quick Start

```bash
# Clone
git clone https://github.com/Unsoph/shade.git
cd shade

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Download YOLOv8n ONNX model
pip install ultralytics
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx')"
mv yolov8n.onnx models/

# Verify
python scripts/setup.py          # Diagnostic checks
python scripts/test_smoke.py     # Headless inference test

# Run
python run.py --source 0              # USB camera
python run.py --source video.mp4      # Video file
python run.py --headless              # No display window
```

## Project Structure

```
shade/
├── run.py                                  # Entry point
├── config/deployment.yaml                  # All runtime configuration
├── models/                                 # ONNX models (gitignored)
├── scripts/
│   ├── setup.py                            # Runtime diagnostic checks
│   └── test_smoke.py                       # Headless inference smoke test
├── src/
│   ├── inference/
│   │   ├── detection.py                    # Detection dataclass
│   │   ├── postprocess.py                  # Letterbox, NMS, COCO labels
│   │   ├── backend_factory.py              # Backend factory (only import point)
│   │   └── backends/
│   │       ├── base_backend.py             # Abstract base class
│   │       ├── onnx_backend.py             # ONNX Runtime CPU (working)
│   │       ├── tflite_backend.py           # TFLite + XNNPACK (stub)
│   │       ├── openvino_backend.py         # OpenVINO (stub)
│   │       └── tensorrt_backend.py         # TensorRT / Jetson (stub)
│   └── video/
│       ├── pipeline.py                     # Capture loop with FPS tracking
│       └── draw.py                         # Bounding box rendering
└── docs/
    ├── PROJECT_STATE.md                    # Current build state
    └── NEXT_STEPS.md                       # Roadmap for next stage
```

## Build Stages

| Stage | Name | Status | Description |
|-------|------|--------|-------------|
| 0 | **Foundation** | ✅ Complete | ONNX inference pipeline with backend abstraction |
| 1 | Health Monitoring | 🔲 Next | Real-time telemetry dashboard (temp, FPS, throttle) |
| 2 | Decision Engine | 🔲 Planned | State machine with hysteresis and cooldown |
| 3 | Adaptive Model Switching | 🔲 Planned | Automatic model ladder traversal under stress |
| 4 | Watchdog Recovery | 🔲 Planned | Crash detection, restart with exponential backoff |
| 5 | Edge Optimization | 🔲 Planned | TFLite benchmarks, thread tuning, INT8 calibration |
| 6 | Observability | 🔲 Planned | Prometheus metrics, Grafana dashboard |
| 7 | Production Hardening | 🔲 Planned | Chaos tests, Docker, Ansible fleet deployment |

## Hardware Targets

| Device | Status | Notes |
|--------|--------|-------|
| Raspberry Pi 5 (8GB) | **Primary** | CPU-only, ONNX Runtime |
| Jetson Nano | Stub | Interface exists, not implemented |
| Jetson Xavier NX | Stub | Interface exists, not implemented |
| Jetson Orin | Stub | Interface exists, not implemented |

## Key Design Decisions

- **Backend abstraction** — All inference goes through `InferenceBackend` ABC.
  Nothing imports a backend directly; everything goes through `BackendFactory`.
- **Config-driven** — All thresholds, paths, and tuning in YAML. Zero magic numbers in code.
- **150-line file limit** — Every file stays under 150 lines. Forced decomposition.
- **Pi-first** — A stable 8 FPS demo on Pi beats an imaginary 60 FPS Jetson project.
- **Thermal-gated upgrades** — Never upgrade during thermal recovery.
- **Atomic hot-swap** — Model swaps execute at frame boundaries, never mid-frame.

## Requirements

- Python 3.10+
- Raspberry Pi 5 (8GB recommended) or any Linux/macOS for development
- USB camera or Pi Camera Module v2/v3
- ONNX Runtime >= 1.17.0
- OpenCV >= 4.8.0

## License

[MIT](LICENSE)
