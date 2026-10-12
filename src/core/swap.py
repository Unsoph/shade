"""Swap primitives shared by the model manager and the controller."""

import logging
import os
import threading
from dataclasses import dataclass

import numpy as np

from src.core.ladder import Rung
from src.inference.backend_factory import create_backend
from src.inference.backends.base_backend import InferenceBackend

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SwapResult:
    idx: int
    rung: Rung
    swap_ms: float   # time spent applying the swap at the frame boundary
    load_s: float    # background preload time (0 for shared-model swaps)
    light: bool


@dataclass
class Pending:
    idx: int
    backend: InferenceBackend
    load_s: float
    light: bool


def build_backend(rung: Rung, config: dict) -> InferenceBackend:
    """Create (not load) the backend for a rung."""
    cfg = {"inference": {
        **config["inference"],
        "backend": rung.backend,
        "input_size": rung.input_size,
        "num_threads": rung.threads or config["inference"]["num_threads"],
        "options": rung.options,
    }}
    return create_backend(cfg)


def warmup(backend: InferenceBackend, rung: Rung) -> None:
    """One dummy inference so the first real frame is not slow."""
    try:
        size = rung.input_size
        backend.infer(np.zeros((size, size, 3), dtype=np.uint8))
    except Exception as exc:  # noqa: BLE001 - warmup is best effort
        logger.warning("Warmup failed for '%s': %s", rung.name, exc)


def lower_thread_priority(nice: int) -> None:
    """Make the calling thread nicer so preloading cannot starve live
    inference. Linux only; silently skipped elsewhere."""
    try:
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), nice)
    except (AttributeError, OSError):
        pass
