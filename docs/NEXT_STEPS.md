# NEXT_STEPS.md — What to build next in SHADE

**Current stage completed:** Stage 0 — Foundation
**Next stage:** Stage 1 — Health Monitoring

---

## Stage 1 — Health Monitoring

### Goal
Real-time telemetry dashboard in the terminal showing FPS, temperature,
memory, and Pi throttle status.

### What to build

1. **`src/core/hardware/base_hw_monitor.py`** — Abstract base:
   `get_cpu_temp()`, `get_gpu_temp()`, `get_memory_percent()`,
   `get_throttle_flags()`, `get_swap_percent()`

2. **`src/core/hardware/raspberry_pi_monitor.py`** — Real implementation:
   - CPU temp: `vcgencmd measure_temp` → parse `temp=XX.X'C`
   - Fallback: `/sys/class/thermal/thermal_zone0/temp ÷ 1000`
   - Throttle: `vcgencmd get_throttled` → parse hex bitmask
     - Bit 0: undervoltage, Bit 1: freq capped, Bit 2: thermal throttle
     - Bits 16-18: historical flags
   - GPU temp: mirrors CPU temp on Pi (log once at startup)
   - Memory: `psutil.virtual_memory()`
   - Swap: `psutil.swap_memory()` — warn >10%, critical >30%

3. **`src/core/hardware/jetson_monitor.py`** — Stub, `NotImplementedError`

4. **`src/core/health_monitor.py`** — Three async monitors:
   - `FPSMonitor`: circular buffer of 30 frame timestamps, rolling average
   - `ThermalMonitor`: reads hardware monitor, polls every 1s
   - `MemoryMonitor`: psutil + swap tracking

5. **`src/core/event_bus.py`** — `asyncio.Queue`, typed events only

6. **`src/core/snapshots.py`** — `HealthSnapshot` dataclass, JSON-serializable

7. **`src/display/console_dashboard.py`** — `rich`-based live table:
   - Updates every 500ms
   - Shows: FPS, CPU temp, throttle status (plain English), memory %,
     swap %, active model, backend name
   - Throttle display: "Clean", "Freq capped", "Thermally throttled",
     "Undervoltage"

### New dependency
- `rich` (for terminal dashboard)

### Demo
Run inference + dashboard side by side. Simulate load with `stress-ng`.
Watch FPS, temperatures, and memory update live.

### What Stage 1 does NOT do
- No thresholds or state transitions (Stage 2)
- No model switching (Stage 3)
- Monitoring and acting are separate concerns

---

## Stage 2 preview
Decision engine with state machine (6 standard states + 2 Pi-specific:
`OS_CONTENTION`, `POWER_WARNING`), hysteresis, cooldown, and SQLite
decision log. State changes are logged, not acted on.

---

## Before starting Stage 1, confirm:
- [ ] Stage 0 demo runs on target hardware (Pi or dev machine + video file)
- [ ] `python scripts/setup.py` shows all green
- [ ] Code committed: `git commit -m "stage-0: foundation — ONNX inference pipeline"`
