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
from collections import deque

from src.core.hardware.base_hw_monitor import HardwareMonitor
from src.core.snapshots import HealthSnapshot

logger = logging.getLogger(__name__)


class FPSTracker:
    """Thread-safe FPS tracker using a circular buffer of timestamps."""

    def __init__(self, buffer_size: int = 30):
        self._timestamps: deque[float] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._frame_count = 0

    def tick(self) -> None:
        """Record a frame timestamp. Called from inference loop."""
        with self._lock:
            self._timestamps.append(time.monotonic())
            self._frame_count += 1

    @property
    def fps(self) -> float:
        """Rolling average FPS over the buffer window."""
        with self._lock:
            if len(self._timestamps) < 2:
                return 0.0
            dt = self._timestamps[-1] - self._timestamps[0]
            if dt <= 0:
                return 0.0
            return (len(self._timestamps) - 1) / dt

    @property
    def frame_count(self) -> int:
        return self._frame_count


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

    def update(self) -> HealthSnapshot:
        """Refresh hardware telemetry and return updated snapshot."""
        cpu_temp = self._hw.get_cpu_temp()
        gpu_temp = self._hw.get_gpu_temp()
        mem_pct = self._hw.get_memory_percent()
        swap_pct = self._hw.get_swap_percent()
        throttle = self._hw.get_throttle_flags()

        with self._lock:
            self._snapshot.timestamp = time.time()
            self._snapshot.fps = self.fps_tracker.fps
            self._snapshot.frame_count = self.fps_tracker.frame_count
            self._snapshot.cpu_temp = cpu_temp
            self._snapshot.gpu_temp = gpu_temp
            self._snapshot.memory_percent = mem_pct
            self._snapshot.swap_percent = swap_pct
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
                self.update()
                self._stop_event.wait(interval)
            logger.info("Health polling stopped.")

        self._stop_event = threading.Event()
        t = threading.Thread(target=_poll_loop, daemon=True, name="health-poll")
        t.start()
        return t

    def stop_polling(self) -> None:
        """Signal the polling thread to stop."""
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
