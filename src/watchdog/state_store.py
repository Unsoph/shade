"""Last-known-good rung: survive restarts without re-triggering a fault.

A rung becomes 'good' after the engine has run stably on it for
`good_after_s` without a critical state. The supervisor starts the next
fresh boot on that rung (if recent) instead of the best one.
"""

import json
import os
import time
from pathlib import Path
from typing import Callable

from src.core.decision.states import Decision, State

UNSTABLE = {State.CRITICAL, State.FAULT, State.POWER_WARNING,
            State.OS_CONTENTION}


class StateStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)

    def save(self, rung_name: str, rung_idx: int, ts: float | None = None):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(
            {"rung": rung_name, "idx": rung_idx, "ts": ts or time.time()}))
        os.replace(tmp, self._path)

    def load(self, max_age_s: float, now: float | None = None) -> dict | None:
        """The stored rung if it exists and is fresh, else None."""
        try:
            data = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return None
        age = (now or time.time()) - data.get("ts", 0)
        return data if 0 <= age <= max_age_s else None


class KnownGoodRecorder:
    """Controller hook: persist a rung once it has been stable long enough."""

    def __init__(self, store: StateStore, rung_names: list[str],
                 good_after_s: float, clock: Callable[[], float] = time.time):
        self._store, self._names = store, rung_names
        self._good_after = good_after_s
        self._clock = clock
        self._rung: int | None = None
        self._since = 0.0
        self._saved: int | None = None

    def __call__(self, decision: Decision) -> None:
        now = self._clock()
        if decision.rung != self._rung or decision.state in UNSTABLE:
            self._rung, self._since = decision.rung, now
            return
        if now - self._since >= self._good_after and self._saved != self._rung:
            self._store.save(self._names[self._rung], self._rung, now)
            self._saved = self._rung
