"""Thread-safe rolling FPS tracker."""

import threading
import time
from collections import deque


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
