"""Fake backend: deterministic latency, no model file.

Used by simulations, the chaos script and tests. Failure injection:
  load_ms          load() sleeps this long (tests background preload)
  fail_load        load() raises (tests failed swaps)
  fail_after       infer() raises after N successful calls (tests crashes)
Latency scales with input area, like a real convolutional detector.
"""

import time

import numpy as np

from src.inference.backends.base_backend import InferenceBackend
from src.inference.detection import Detection

BASE_SIZE = 640


class FakeBackend(InferenceBackend):
    def __init__(self, input_size: int = BASE_SIZE, latency_ms: float = 25.0,
                 fail_load: bool = False, fail_after: int = 0,
                 mem_mb: int = 10, load_ms: float = 0.0, **_ignored):
        self._input_size = input_size
        self._latency_s = latency_ms / 1000.0 * (input_size / BASE_SIZE) ** 2
        self._fail_load = fail_load
        self._fail_after = fail_after
        self._mem_mb = mem_mb
        self._load_s = load_ms / 1000.0
        self._loaded = False
        self.calls = 0
        self.load_seconds = 0.0

    @property
    def input_size(self) -> int:
        return self._input_size

    def load(self, model_path: str) -> None:
        time.sleep(self._load_s)
        if self._fail_load:
            raise RuntimeError("fake load failure")
        self._loaded = True

    def infer(self, frame: np.ndarray) -> list[Detection]:
        if not self._loaded:
            raise RuntimeError("No model loaded. Call load() first.")
        self.calls += 1
        if self._fail_after and self.calls > self._fail_after:
            raise RuntimeError("fake inference failure")
        time.sleep(self._latency_s)
        h, w = frame.shape[:2]
        return [Detection(w // 4, h // 4, w // 2, h // 2, 0.9, 0, "person")]

    def unload(self) -> None:
        self._loaded = False

    @property
    def backend_name(self) -> str:
        return "fake"

    @property
    def vram_mb(self) -> int:
        return self._mem_mb if self._loaded else 0
