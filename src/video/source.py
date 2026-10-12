"""Frame sources: camera, video file or synthetic, with self-healing.

Live sources are read on a capture thread that keeps only the newest
frame, so a slow detector never sees stale buffered frames. A failed
read reopens the device with exponential backoff (camera_reconnect
events). Files are read inline and end with EOF (or loop).
"""

import logging
import threading
from typing import Callable

import cv2
import numpy as np

from src.video.synthetic import SyntheticCapture, parse_spec

logger = logging.getLogger(__name__)
LIVE_PREFIXES = ("rtsp://", "http://", "https://")


def default_opener(source) -> object:
    """Open a cv2 capture or synthetic capture for the given source."""
    if isinstance(source, str) and (spec := parse_spec(source)):
        return SyntheticCapture(*spec)
    if isinstance(source, str) and source.isdigit():
        source = int(source)
    cap = cv2.VideoCapture(source)
    if isinstance(source, int):
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def is_live(source) -> bool:
    return isinstance(source, int) or source.isdigit() or \
        source.startswith(("synthetic",) + LIVE_PREFIXES)


class FrameSource:
    def __init__(self, source, cam_cfg: dict, opener: Callable = default_opener,
                 on_event: Callable[[str, dict], None] | None = None):
        self._source = source
        self._cfg = cam_cfg
        self._open = opener
        self._on_event = on_event or (lambda kind, detail: None)
        self.live = is_live(source)
        self.eof = False
        self._cap = None
        self._stop = threading.Event()
        self._reopen = threading.Event()
        self._cond = threading.Condition()
        self._latest: np.ndarray | None = None
        self._seq = self._seen = 0
        self._thread: threading.Thread | None = None
        self.reconnects = 0

    def start(self) -> "FrameSource":
        self._cap = self._open(self._source)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {self._source}")
        logger.info("Video source opened: %s (%s)", self._source,
                    "live" if self.live else "file")
        if self.live:
            self._thread = threading.Thread(target=self._capture_loop,
                                            daemon=True, name="capture")
            self._thread.start()
        return self

    def read(self, timeout: float = 1.0) -> np.ndarray | None:
        """Next frame, or None (EOF for files, no new frame for live)."""
        if not self.live:
            return self._read_file()
        with self._cond:
            if not self._cond.wait_for(lambda: self._seq > self._seen, timeout):
                return None
            self._seen = self._seq
            return self._latest

    def request_reopen(self) -> None:
        """Ask the capture thread to reopen the device (e.g. frozen feed)."""
        self._reopen.set()

    def close(self) -> None:
        self._stop.set()
        self._reopen.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap is not None:
            self._cap.release()

    # -- internals -----------------------------------------------------
    def _read_file(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        if ok:
            return frame
        if self._cfg["loop_video"]:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
            if ok:
                return frame
        self.eof = True
        return None

    def _capture_loop(self) -> None:
        backoff = self._cfg["reconnect_initial_s"]
        while not self._stop.is_set():
            if self._cap is None or self._reopen.is_set():
                self._reopen.clear()
                if self._stop.is_set():
                    break
                if not self._reconnect():
                    self._stop.wait(backoff)
                    backoff = min(backoff * 2, self._cfg["reconnect_max_s"])
                    continue
                backoff = self._cfg["reconnect_initial_s"]
            ok, frame = self._cap.read()
            if not ok or frame is None:
                logger.warning("Camera read failed; will reconnect.")
                self._drop()
                continue
            with self._cond:
                self._latest, self._seq = frame, self._seq + 1
                self._cond.notify_all()

    def _drop(self) -> None:
        cap, self._cap = self._cap, None
        if cap is not None:
            cap.release()

    def _reconnect(self) -> bool:
        if not self._cfg["reconnect"]:
            self.eof = True
            self._stop.set()
            return False
        self._drop()
        try:
            cap = self._open(self._source)
        except Exception as exc:  # noqa: BLE001 - a bad open is just a failed attempt
            logger.warning("Camera open raised: %s", exc)
            self._on_event("camera_open_failed", {"error": str(exc)})
            return False
        if cap.isOpened():
            self._cap = cap
            self.reconnects += 1
            logger.info("Camera reconnected (#%d).", self.reconnects)
            self._on_event("camera_reconnect", {"count": self.reconnects})
            return True
        cap.release()
        self._on_event("camera_open_failed", {"source": str(self._source)})
        return False
