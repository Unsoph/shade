"""Input health: detect a frozen, dark or missing camera feed.

These are failures a model swap cannot fix, so they raise a FAULT state
and trigger a camera reopen instead. Frozen means near-identical frames
(sensor noise survives downsampling, so a live static scene is not flagged).
"""

import time
from typing import Callable

import cv2
import numpy as np

THUMB = (32, 24)


class InputHealth:
    def __init__(self, cfg: dict, clock: Callable[[], float] = time.monotonic):
        self._cfg = cfg
        self._clock = clock
        self._prev: np.ndarray | None = None
        self._frozen_since: float | None = None
        self._dark_since: float | None = None
        self._last_frame_at = clock()
        self.fault = ""

    def update(self, frame: np.ndarray) -> str:
        """Feed a frame; returns '' | 'frozen' | 'dark'."""
        now = self._clock()
        self._last_frame_at = now
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        thumb = cv2.resize(gray, THUMB, interpolation=cv2.INTER_AREA)
        thumb = thumb.astype(np.float32)

        if self._prev is not None and \
                float(np.abs(thumb - self._prev).mean()) < self._cfg["frozen_eps"]:
            self._frozen_since = self._frozen_since or now
        else:
            self._frozen_since = None
        self._prev = thumb

        if float(thumb.mean()) < self._cfg["dark_level"]:
            self._dark_since = self._dark_since or now
        else:
            self._dark_since = None

        self.fault = self._classify(now)
        return self.fault

    def no_frame(self) -> str:
        """Call when a read produced nothing; returns 'lost' after lost_s."""
        if self._clock() - self._last_frame_at >= self._cfg["lost_s"]:
            self.fault = "lost"
        return self.fault

    def _classify(self, now: float) -> str:
        if self._frozen_since is not None and \
                now - self._frozen_since >= self._cfg["frozen_s"]:
            return "frozen"
        if self._dark_since is not None and \
                now - self._dark_since >= self._cfg["dark_s"]:
            return "dark"
        return ""
