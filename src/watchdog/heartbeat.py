"""Heartbeat file: proof of life from the inference loop.

The engine writes it from the frame loop (not a side thread), so a hung
inference stops the heartbeat. Writes are atomic (temp file + rename).
"""

import json
import os
import time
from pathlib import Path
from typing import Callable


class Heartbeat:
    def __init__(self, path: str | Path, interval_s: float = 0.5,
                 clock: Callable[[], float] = time.time):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._interval = interval_s
        self._clock = clock
        self._last = 0.0

    def beat(self, frames: int = 0, **extra) -> None:
        """Write a heartbeat if at least `interval_s` has passed."""
        now = self._clock()
        if now - self._last < self._interval:
            return
        self._last = now
        payload = {"pid": os.getpid(), "ts": now, "frames": frames, **extra}
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, self._path)


def read_heartbeat(path: str | Path) -> dict | None:
    """Latest heartbeat, or None if missing/corrupt."""
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
