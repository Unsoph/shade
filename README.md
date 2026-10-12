<p align="center">
  <img src="https://img.shields.io/badge/Target-Raspberry%20Pi%205-c51a4a?style=for-the-badge&logo=raspberrypi&logoColor=white" />
  <img src="https://img.shields.io/badge/Runtime-ONNX%20Runtime-007CFF?style=for-the-badge&logo=onnx&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Stages-0--7%20implemented-2ea44f?style=for-the-badge" />
</p>

# SHADE — Self-Healing Adaptive Deployment Engine

An operations layer for edge AI inference. SHADE watches the device (temperature,
throttle flags, memory, FPS, camera health), steps the detector down a
**degradation ladder** before the hardware forces it to, steps back up only when
it is safe, restarts the engine if it crashes or hangs, and records every decision
in an audit database you can query.

> **Status, stated plainly.** All eight stages are implemented and covered by 86
> automated tests (84 run anywhere, 2 need a local model file) plus fault-injection runs on a *simulated* machine. **Nothing
> has been measured on a real Raspberry Pi 5 yet.** Thresholds are reasoned defaults,
> not tuned values, and no benchmark numbers are claimed. See
> [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) for the protocol that produces them.

## What is implemented

| Stage | Capability | Where |
|-------|------------|-------|
| 0 | YOLOv8 ONNX detection (letterbox, pure-NumPy class-aware NMS), backend abstraction | `src/inference/` |
| 1 | Health monitor: CPU temp, `vcgencmd get_throttled` (psutil/sysfs fallback), RAM/swap, FPS | `src/core/hardware/`, `health_monitor.py` |
| 2 | Decision engine: pressure level 0-3, hysteresis, dwell, cooldown, slope anticipation, one-step upgrades, SQLite audit log | `src/core/decision/` |
| 3 | Ladder + `ModelManager`: background preload (RAM headroom check, warmup, low priority), atomic swap at a frame boundary, failure fallback | `src/core/ladder.py`, `model_manager.py` |
| 4 | Watchdog: heartbeat file, supervisor with backoff and hang detection, restart on the emergency rung, last-known-good state, systemd `sd_notify` | `src/watchdog/` |
| 5 | Benchmark (p50/p95/p99, sustained drift), INT8 quantization, model export, agreement scoring | `src/bench/`, `scripts/` |
| 6 | Read-only HTTP: `/metrics` (Prometheus), `/status`, `/decisions`, live page | `src/observability/` |
| 7 | Chaos runs, CI (py3.10-3.12), line-limit check, Dockerfile, systemd unit | `scripts/chaos.py`, `.github/`, `deploy/` |

Also: input health (frozen / dark / lost camera → reconnect with backoff), frame-skip
rungs that reuse the last detections, and a scripted hardware simulator so every
behaviour can be demonstrated without a hot Pi.

## Quick start

```bash
git clone https://github.com/Unsoph/shade.git && cd shade
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest                                   # 84 pass, 2 skip without a model; ~30 s

# Watch SHADE degrade and recover with no hardware and no models:
python run.py --simulate thermal_ramp --speed 20 --fake --headless \
    --skip-setup --source synthetic:320x240@30 --serve
# then open http://127.0.0.1:9108/  (metrics at /metrics)

python scripts/chaos.py                            # fault-injection summary
```

With a real model and camera:

```bash
mkdir -p models && wget -P models \
  https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.onnx
python run.py --source 0                           # USB camera
python run.py --source video.mp4 --headless --supervised --serve
```

With only `yolov8n.onnx` present the ladder has two rungs (full rate, then
every-2nd-frame). Rungs whose model file is missing are skipped. For the full
ladder, generate the extra models **on your own machine** (needs `ultralytics`):

```bash
python scripts/export_models.py                    # yolov8n 640 + 320
python scripts/quantize_int8.py --model models/yolov8n_320.onnx \
    --calib <folder of ~50 scene images> --out models/yolov8n_320_int8.onnx
python scripts/eval_agreement.py --images <folder>  # does the cheap rung still agree?
python scripts/benchmark.py --source <folder> --threads 1,2,4 --sustained 300
```

Quantization note: quantizing YOLOv8's Detect head zeroed all class scores in our
test, so `quantize_int8.py` keeps the head in FP32 by default. INT8 is also not
guaranteed to be faster on the Pi 5's CPU stack ([related work](docs/DESIGN.md#related-work));
measure before trusting it.

## How the decision logic behaves

`ladder` is ordered best to worst. Each poll the engine maps signals to a pressure
level and a minimum rung (`policy.level_to_rung`):

- **Escalate** when temperature, throttle flags, memory/swap, FPS or camera health
  cross a band for `confirm_samples` polls and `dwell_s` has passed. A temperature
  rising faster than `rise_c_per_s` while already warm escalates one level early.
- **Critical** (≥ `critical_c`, active throttling) bypasses confirmation and dwell.
- **Recover** one rung at a time, only below `upgrade_gate_c` with no throttle flags,
  after `recover_hold_s`; a `cooldown_s` follows every change. This prevents the
  flapping a naive threshold causes.
- Undervoltage is reported as `POWER_WARNING` (a power-supply fault, not something a
  smaller model fixes); memory/swap pressure shows as `OS_CONTENTION`.

Every change, swap, reconnect and restart lands in `logs/shade.db`
(`events` table) with the reasons and the signal values that caused it.

## Supervision and observability

`--supervised` runs the engine as a child. It must write a heartbeat from its frame
loop (also while idle); silence beyond `hang_timeout_s` gets it killed and restarted
with exponential backoff, starting on the emergency rung (or the last rung that ran
stably for `good_after_s`). After `max_restarts` consecutive unstable restarts it
gives up and exits non-zero so systemd can take over (`deploy/shade.service`).

`--serve [PORT]` exposes `/`, `/status`, `/decisions`, `/metrics`, `/healthz` on
`127.0.0.1:9108`. It is **unauthenticated**; use `--serve-host` or a reverse proxy
only on a trusted network. No Grafana dashboard ships; the metrics are standard
Prometheus text, so one is a straightforward addition.

## Verified vs not verified

| Verified here | Not verified |
|---------------|--------------|
| Unit + integration tests (84 pass, 2 need a local model), CI matrix 3.10-3.12 | Any run on a real Pi 5 / Jetson |
| Real yolov8n output: 4 persons + 1 bus on the standard test image | Threshold tuning against real thermal behaviour |
| Simulated thermal ramp/spike, undervoltage, memory pressure: degrade, recover one rung at a time (`scripts/chaos.py`) | FPS/latency/accuracy of the 320 and INT8 rungs |
| Supervisor with real child processes: crash, hang, then success | Docker image build; Pi camera (`picamera2`) path |
| INT8 quantization pipeline runs and detections agree on the one test image | Preload contention on the Pi (on a 2-core test box a background load caused a 538 ms frame gap vs 95 ms median; `preload_nice` is untuned) |
| Jetson / TFLite / OpenVINO / TensorRT: stubs only | Jetson support |

Differences from the original plan: the emergency rung is a 320-px INT8 YOLOv8n
(NanoDet-Plus was dropped; one model family keeps the post-processing shared),
and the upgrade gate is 65 °C (`policy.upgrade_gate_c`) rather than 55 °C so that
recovery is not blocked in warm rooms or cases; it is configurable and untuned.

## Layout

```
run.py                 entry point (--simulate --fake --supervised --serve ...)
config/deployment.yaml every tunable, documented
src/inference/         preprocess, NMS, backends (onnx, fake; others are stubs)
src/core/              config, decision engine, ladder, model manager, simulation
src/video/             frame source with reconnect, synthetic camera, pipeline
src/watchdog/          heartbeat, supervisor, last-known-good store
src/observability/     stdlib HTTP server and Prometheus rendering
src/bench/             stats, matching, benchmark runner
scripts/               benchmark, quantize, export, eval, chaos, demos, line-limit
deploy/ Dockerfile     systemd unit; container image (untested)
docs/                  DESIGN, EXPERIMENTS, PROJECT_STATE, NEXT_STEPS
```

Conventions: no source file over 150 lines (`scripts/check_line_limit.py`), all
thresholds in config, every stage leaves a runnable system.

## License

[MIT](LICENSE)
