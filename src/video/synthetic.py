"""Synthetic camera: a VideoCapture look-alike for simulations and tests."""

import re
import time

import cv2
import numpy as np

SPEC = re.compile(r"^synthetic(?::(\d+)x(\d+))?(?:@(\d+(?:\.\d+)?))?$")
DEFAULT_FPS = 30.0


def parse_spec(spec: str):
    """'synthetic:640x480@15' -> (640, 480, 15.0); None if not synthetic."""
    m = SPEC.match(spec)
    if not m:
        return None
    w, h, fps = m.groups()
    return int(w or 640), int(h or 480), float(fps or DEFAULT_FPS)


class SyntheticCapture:
    """Moving rectangle over a gradient, paced at `fps`."""

    def __init__(self, width=640, height=480, fps=DEFAULT_FPS):
        self._w, self._h = width, height
        self._period = 1.0 / fps if fps > 0 else 0.0
        self._next = time.monotonic()
        self._n = 0
        xs = np.linspace(40, 200, width, dtype=np.uint8)
        self._base = np.tile(xs, (height, 1))[:, :, None].repeat(3, axis=2)

    def isOpened(self) -> bool:
        return True

    def read(self):
        if self._period:
            wait = self._next - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._next = max(self._next + self._period, time.monotonic())
        frame = self._base.copy()
        x = (self._n * 7) % max(1, self._w - 80)
        cv2.rectangle(frame, (x, self._h // 3), (x + 80, self._h // 3 + 120),
                      (30, 60, 220), -1)
        self._n += 1
        return True, frame

    def release(self) -> None:
        pass
