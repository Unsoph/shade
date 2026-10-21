"""Move last detections along with the scene on frames the detector skips.

For each box, the translation between the anchor frame (where the detector
last ran) and the current frame is estimated by phase correlation on that
box's region of a small grayscale copy. Cheap (a few small FFTs) next to a
detector forward pass. Pure translation only: scale or rotation changes are
not tracked, and the anchor is refreshed at every real detection.
"""

import cv2
import numpy as np

from src.inference.detection import Detection

SMALL_WIDTH = 192
MIN_ROI = 8


def small_gray(frame: np.ndarray, width: int = SMALL_WIDTH):
    """Downscaled float32 grayscale image and the scale factor used."""
    scale = width / frame.shape[1]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return small.astype(np.float32), scale


class BoxShifter:
    def __init__(self, min_response: float = 0.15, max_shift_frac: float = 0.5):
        self.min_response = min_response
        self.max_shift_frac = max_shift_frac
        self._ref: np.ndarray | None = None
        self._scale = 1.0
        self._dets: list[Detection] = []

    def anchor(self, frame: np.ndarray, dets: list[Detection]) -> None:
        self._ref, self._scale = small_gray(frame)
        self._dets = list(dets)

    def shift(self, frame: np.ndarray) -> list[Detection]:
        """Anchor detections moved to where they are in `frame`."""
        if self._ref is None or not self._dets:
            return list(self._dets)
        cur, _ = small_gray(frame)
        h, w = cur.shape
        out = []
        for d in self._dets:
            dx, dy = self._box_shift(cur, d, w, h)
            s = 1.0 / self._scale
            fh, fw = frame.shape[:2]
            out.append(Detection(
                int(np.clip(d.x1 + dx * s, 0, fw - 1)),
                int(np.clip(d.y1 + dy * s, 0, fh - 1)),
                int(np.clip(d.x2 + dx * s, 0, fw - 1)),
                int(np.clip(d.y2 + dy * s, 0, fh - 1)),
                d.confidence, d.class_id, d.label))
        return out

    def _box_shift(self, cur, d: Detection, w: int, h: int):
        k = self._scale
        x1, x2 = int(max(d.x1 * k, 0)), int(min(d.x2 * k, w))
        y1, y2 = int(max(d.y1 * k, 0)), int(min(d.y2 * k, h))
        if x2 - x1 < MIN_ROI or y2 - y1 < MIN_ROI:
            return 0.0, 0.0
        a, b = self._ref[y1:y2, x1:x2], cur[y1:y2, x1:x2]
        win = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
        (dx, dy), response = cv2.phaseCorrelate(a, b, win)
        limit = self.max_shift_frac * max(a.shape)
        if response < self.min_response or abs(dx) > limit or abs(dy) > limit:
            return 0.0, 0.0
        return dx, dy
