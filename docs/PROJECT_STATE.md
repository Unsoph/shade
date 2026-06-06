# PROJECT_STATE.md — Current State of SHADE

**Last updated:** 2026-06-06
**Current stage:** Stage 0 — Foundation (COMPLETE)
**Build target:** Raspberry Pi 5 (8GB), CPU-only inference
**Dev machine:** macOS (development), Pi 5 (deployment target)

---

## What exists now

### Inference layer (`src/inference/`)
- **Backend ABC** (`base_backend.py`): defines `load()`, `infer()`, `unload()`,
  `backend_name`, `vram_mb` — the contract all backends implement.
- **ONNX Backend** (`onnx_backend.py`): full YOLOv8 implementation with
  letterbox preprocessing, transposed-output postprocessing, OpenCV NMS.
  Logs `SD_IO_SLOW` if model load exceeds 5s (Pi SD card detection).
  `intra_op_num_threads=4` for Pi 5's quad-core A76.
- **Backend Factory** (`backend_factory.py`): reads config, returns the
  correct backend. Only place that imports concrete backends.
- **Stubs**: TFLite, OpenVINO, TensorRT — exist so the registry knows about
  them. All raise `NotImplementedError`.
- **Detection** (`detection.py`): frozen dataclass with slots.

### Video layer (`src/video/`)
- **Pipeline** (`pipeline.py`): OpenCV capture loop with USB/Pi Camera
  auto-detection, bounding box rendering, smoothed FPS counter,
  headless mode, camera disconnect handling.

### Config (`config/`)
- **deployment.yaml**: device type, backend selection, model path,
  input size, thresholds, camera settings, logging config.

### Scripts
- **setup.py**: diagnostic table of all runtimes, Pi model detection,
  JetPack detection, vcgencmd temp check. Exits non-zero if no runtime.

### Entry point
- **run.py**: CLI with `--source`, `--config`, `--headless`, `--max-frames`,
  `--skip-setup` flags. Clear error if model file missing.

---

## What does NOT exist yet (by design)

- No health monitoring (Stage 1)
- No state machine or thresholds (Stage 2)
- No model hot-swap or model registry (Stage 3)
- No watchdog or recovery (Stage 4)
- No benchmarking or TFLite comparison (Stage 5)
- No Prometheus metrics or Grafana (Stage 6)
- No chaos tests or Docker (Stage 7)

---

## Known limitations

1. **No model file included** — user must download `yolov8n.onnx` manually.
2. **macOS dev** — camera and vcgencmd features are Pi-specific;
   pipeline runs on macOS with a video file source.
3. **Single backend** — only ONNX Runtime is functional. Others are stubs.
4. **No error recovery** — camera disconnect ends the loop (reconnect
   logic is deferred to Stage 4).
