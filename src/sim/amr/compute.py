"""Onboard compute model: which camera frames get a detection, and the CPU load.

Uses SHADE's real Scheduler on the twin's rendered camera frames, so the
content gate reacts to what the robot actually sees (parked = static scene,
driving = motion). Detections cost CPU-seconds per rung (assumed until E1);
throttling stretches that cost, and a detection that no longer fits in the
second's CPU budget is dropped, as on a saturated Pi.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from src.video.scheduler import Scheduler

TINY = (64, 48)


@dataclass
class Window:
    util: float          # mean CPU utilisation over the window, 0..1
    detections: int      # detector runs completed
    wanted: int          # frames the scheduler wanted to detect on
    dropped: int         # wanted but no CPU budget left
    frames: int
    motion: float        # mean grey-level change between frames (0-255)


class ComputeModel:
    def __init__(self, compute: dict, scheduling: dict, detect_every: list[int]):
        if len(compute["det_cost_s"]) != len(detect_every):
            raise ValueError("compute.det_cost_s needs one entry per ladder rung")
        self.c = compute
        self.every = detect_every
        self.scheduler = Scheduler(scheduling)
        self._prev: np.ndarray | None = None
        self._open(0, 1.0, False, 1.0)

    def _open(self, rung: int, scale: float, swapping: bool, span_s: float):
        self.rung, self.scale, self.span = rung, scale, span_s
        overhead = self.c["base_util"] + (self.c["swap_util"] if swapping else 0.0)
        self.overhead = min(overhead, 1.0)
        self.budget = max(1.0 - self.overhead, 0.0) * span_s
        self.used = 0.0
        self.n = {"det": 0, "want": 0, "drop": 0, "frames": 0}
        self._motion = []

    def start_window(self, rung: int, scale: float, swapping: bool,
                     span_s: float = 1.0) -> None:
        """Begin a decision window on `rung` at clock `scale` (<1 = throttled)."""
        self._open(rung, scale, swapping, span_s)

    def on_frame(self, frame: np.ndarray) -> bool:
        """Process one camera frame; True if the detector ran on it."""
        self.n["frames"] += 1
        tiny = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), TINY,
                          interpolation=cv2.INTER_AREA).astype(np.float32)
        if self._prev is not None:
            self._motion.append(float(np.abs(tiny - self._prev).mean()))
        self._prev = tiny
        if not self.scheduler.should_detect(frame, self.every[self.rung]):
            return False
        self.n["want"] += 1
        cost = self.c["det_cost_s"][self.rung] / max(self.scale, 1e-3)
        if self.used + cost > self.budget:
            self.n["drop"] += 1
            return False
        self.used += cost
        self.n["det"] += 1
        self.scheduler.after_detect(frame, [])
        return True

    def end_window(self) -> Window:
        util = self.overhead + self.used / self.span
        motion = float(np.mean(self._motion)) if self._motion else 0.0
        n = self.n
        return Window(min(util, 1.0), n["det"], n["want"], n["drop"],
                      n["frames"], motion)
