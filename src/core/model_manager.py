"""Model manager: preload in the background, swap at a frame boundary.

The pipeline calls poll() once per frame; a ready backend is swapped in
with one reference assignment, so inference never blocks on a model load.
Rungs sharing a model (frame-skip variants) swap without any load.
"""

import logging
import threading
import time
from typing import Callable

import psutil

from src.core.ladder import Rung
from src.core.swap import (Pending, SwapResult, build_backend,
                           lower_thread_priority, warmup)
from src.inference.backends.base_backend import InferenceBackend

logger = logging.getLogger(__name__)
MB = 1024 * 1024


class ModelManager:
    def __init__(self, rungs: list[Rung], config: dict,
                 on_failure: Callable[[int, str], None] | None = None):
        self._rungs = rungs
        self._config = config
        self._settings = config["ladder_settings"]
        self.on_failure = on_failure
        self._lock = threading.Lock()
        self._backend: InferenceBackend | None = None
        self._idx = -1
        self._target: int | None = None
        self._pending: Pending | None = None
        self._worker: threading.Thread | None = None

    # -- read side (inference thread) ---------------------------------
    @property
    def backend(self) -> InferenceBackend:
        if self._backend is None:
            raise RuntimeError("ModelManager has no loaded backend.")
        return self._backend

    @property
    def index(self) -> int:
        return self._idx

    @property
    def rung(self) -> Rung:
        return self._rungs[self._idx]

    def poll(self) -> SwapResult | None:
        """Apply a ready swap. Call at a frame boundary."""
        if self._pending is None:
            return None
        start = time.perf_counter()
        with self._lock:
            pend, self._pending = self._pending, None
            if pend is None:
                return None
            old, self._backend, self._idx = self._backend, pend.backend, pend.idx
        swap_ms = (time.perf_counter() - start) * 1000.0
        if old is not None and old is not pend.backend:
            threading.Thread(target=old.unload, daemon=True,
                             name="model-unload").start()
        logger.info("Swapped to rung %d '%s' (swap %.3f ms, load %.2fs)",
                    pend.idx, self._rungs[pend.idx].name, swap_ms, pend.load_s)
        return SwapResult(pend.idx, self._rungs[pend.idx], swap_ms,
                          pend.load_s, pend.light)

    # -- write side ----------------------------------------------------
    def load_initial(self, idx: int) -> None:
        """Synchronously load the starting rung."""
        self._backend, self._idx = self._load(self._rungs[idx]), idx

    def request(self, idx: int) -> None:
        """Ask for a rung; the latest request wins."""
        with self._lock:
            self._target = None if idx == self._idx and not self._pending else idx
            if self._target is None:
                return
            if self._worker is not None:
                return
            self._worker = threading.Thread(target=self._run, daemon=True,
                                            name="model-preload")
            self._worker.start()

    def close(self) -> None:
        with self._lock:
            self._target = None
        if self._worker is not None:
            self._worker.join(timeout=10)
        if self._backend:
            self._backend.unload()

    # -- worker --------------------------------------------------------
    def _run(self) -> None:
        lower_thread_priority(self._settings["preload_nice"])
        while True:
            with self._lock:
                idx, self._target = self._target, None
                if idx is None:
                    self._worker = None
                    return
            self._prepare(idx)

    def _prepare(self, idx: int) -> None:
        rung, current = self._rungs[idx], self.rung
        if rung.same_model(current):
            self._set_pending(Pending(idx, self.backend, 0.0, True))
            return
        need = rung.size_mb() * self._settings["memory_factor"]
        free = psutil.virtual_memory().available / MB
        reserve = self._settings["min_free_mb_after_load"]
        if rung.backend != "fake" and free - need < reserve:
            self._fail(idx, f"low memory: {free:.0f}MB free, need ~{need:.0f}MB")
            return
        start = time.monotonic()
        try:
            backend = self._load(rung)
        except Exception as exc:  # noqa: BLE001 - any load failure is a failed swap
            self._fail(idx, f"load failed: {exc}")
            return
        load_s = time.monotonic() - start
        with self._lock:
            superseded = self._target is not None and self._target != idx
        if superseded:
            backend.unload()
            return
        self._set_pending(Pending(idx, backend, load_s, False))

    def _set_pending(self, pend: Pending) -> None:
        with self._lock:
            stale, self._pending = self._pending, pend
        if stale is not None and stale.backend is not pend.backend \
                and not stale.light:
            stale.backend.unload()

    def _load(self, rung: Rung) -> InferenceBackend:
        backend = build_backend(rung, self._config)
        backend.load(rung.model_path())
        if self._settings["warmup"]:
            warmup(backend, rung)
        return backend

    def _fail(self, idx: int, reason: str) -> None:
        logger.error("Swap to rung %d failed: %s", idx, reason)
        if self.on_failure:
            self.on_failure(idx, reason)
