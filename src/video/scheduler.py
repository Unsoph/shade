"""When to run the detector, and what to show on frames that skip it.

The ladder fixes a *budget*: at most one detection every `detect_every`
frames. The scheduler spends that budget well:
  - gate:  when the scene is static (small frame difference against the
           anchor frame), stretch the interval up to `static_factor` x
           the budget, saving compute without losing accuracy;
  - shift: on skipped frames, move last boxes with the scene (BoxShifter)
           instead of freezing them.
Both are off by default; behaviour then equals plain frame skipping.
"""

import cv2
import numpy as np

from src.video.propagate import BoxShifter

GATE_SIZE = (64, 48)


class Scheduler:
    def __init__(self, cfg: dict):
        self.gate = cfg["gate"]
        self.shift = cfg["shift"]
        self.motion_thr = cfg["motion_threshold"]
        self.static_factor = max(1, int(cfg["static_factor"]))
        self._shifter = BoxShifter(cfg["min_response"]) if self.shift else None
        self._since = 10 ** 9  # frames since the last detection
        self._anchor_small: np.ndarray | None = None
        self.detections_run = 0
        self.frames_seen = 0

    def _tiny(self, frame):
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.resize(g, GATE_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)

    def motion(self, frame) -> float:
        """Mean absolute grey-level change vs the anchor frame (0-255)."""
        if self._anchor_small is None:
            return float("inf")
        return float(np.abs(self._tiny(frame) - self._anchor_small).mean())

    def should_detect(self, frame, every: int) -> bool:
        self.frames_seen += 1
        due = self._since >= every
        if due and self.gate and self._since < every * self.static_factor:
            due = self.motion(frame) >= self.motion_thr
        self._since += 1
        return due

    def after_detect(self, frame, dets) -> None:
        self._since = 1
        self.detections_run += 1
        if self.gate:
            self._anchor_small = self._tiny(frame)
        if self._shifter:
            self._shifter.anchor(frame, dets)

    def on_skip(self, frame, last_dets):
        return self._shifter.shift(frame) if self._shifter else last_dets
