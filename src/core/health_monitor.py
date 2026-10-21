"""Health monitor — collects FPS, thermal, memory, and throttle data.

Three monitors run as threads (CPU-bound telemetry reads):
  - FPSMonitor: circular buffer of frame timestamps, rolling average
  - ThermalMonitor: polls hardware monitor every interval
  - MemoryMonitor: psutil memory + swap tracking

Publishes HealthSnapshot to the event bus at a configurable rate.
"""

import logging
import threading
import time
from typing import Callable

from src.core.fps import FPSTracker
from src.core.hardware.base_hw_monitor import HardwareMonitor
from src.core.snapshots import HealthSnapshot

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Aggregates all health data into snapshots.

    Call update() periodically (e.g. every 500ms) to refresh
    hardware telemetry. Call snapshot() to get current state.
    FPS is updated externally via fps_tracker.tick().
    """

    def __init__(self, hw_monitor: HardwareMonitor):
        self._hw = hw_monitor
        self.fps_tracker = FPSTracker(buffer_size=30)
        self._snapshot = HealthSnapshot(platform=hw_monitor.get_platform_name())
        self._lock = threading.Lock()
        self._listeners: list[Callable[[HealthSnapshot], None]] = []
        self._stop_event = threading.Event()

    def add_listener(self, fn: Callable[[HealthSnapshot], None]) -> None:
        """Call fn(snapshot) after every polled update (poll thread)."""
        self._listeners.append(fn)

    def set_control(self, state: str | None = None, rung: int | None = None,
                    rung_name: str | None = None) -> None:
        """Control-plane fields written by the controller."""
        with self._lock:
            if state is not None:
                self._snapshot.state = state
            if rung is not None:
                self._snapshot.rung = rung
                self._snapshot.model_tier = rung
            if rung_name is not None:
                self._snapshot.rung_name = rung_name

    def set_runtime(self, input_fault: str | None = None,
                    detections: int | None = None,
                    swap_stall_ms: float | None = None) -> None:
        """Pipeline-side fields."""
        with self._lock:
            if input_fault is not None:
                self._snapshot.input_fault = input_fault
            if detections is not None:
                self._snapshot.detections = detections
            if swap_stall_ms is not None:
                self._snapshot.swap_stall_ms = swap_stall_ms

    def update(self) -> HealthSnapshot:
        """Refresh hardware telemetry and return updated snapshot."""
        cpu_temp = self._hw.get_cpu_temp()
        gpu_temp = self._hw.get_gpu_temp()
        mem_pct = self._hw.get_memory_percent()
        swap_pct = self._hw.get_swap_percent()
        cpu_util = getattr(self._hw, "get_cpu_util", lambda: 0.0)()
        throttle = self._hw.get_throttle_flags()

        with self._lock:
            self._snapshot.timestamp = time.time()
            self._snapshot.fps = self.fps_tracker.fps
            self._snapshot.frame_count = self.fps_tracker.frame_count
            self._snapshot.cpu_temp = cpu_temp
            self._snapshot.gpu_temp = gpu_temp
            self._snapshot.memory_percent = mem_pct
            self._snapshot.swap_percent = swap_pct
            self._snapshot.cpu_util = cpu_util
            self._snapshot.throttle_status = throttle.human_readable
            self._snapshot.throttle_raw = throttle.raw_hex

        return self.snapshot()

    def set_model_info(
        self, model_name: str, backend: str, tier: int, vram: int,
    ) -> None:
        """Update model info in the snapshot (called on model load/swap)."""
        with self._lock:
            self._snapshot.active_model = model_name
            self._snapshot.backend_name = backend
            self._snapshot.model_tier = tier
            self._snapshot.vram_mb = vram

    def snapshot(self) -> HealthSnapshot:
        """Return a copy of the current snapshot."""
        with self._lock:
            return HealthSnapshot(**self._snapshot.to_dict())

    def start_polling(self, interval: float = 1.0) -> threading.Thread:
        """Start a background thread that polls hardware at interval.

        Returns the thread (already started).
        """
        def _poll_loop():
            logger.info("Health polling started (interval=%.1fs)", interval)
            while not self._stop_event.is_set():
                snap = self.update()
                for fn in self._listeners:
                    try:
                        fn(snap)
                    except Exception:  # noqa: BLE001 - a listener must not kill polling
                        logger.exception("Health listener failed.")
                self._stop_event.wait(interval)
            logger.info("Health polling stopped.")

        self._stop_event.clear()
        t = threading.Thread(target=_poll_loop, daemon=True, name="health-poll")
        t.start()
        return t

    def stop_polling(self) -> None:
        """Signal the polling thread to stop."""
        self._stop_event.set()
