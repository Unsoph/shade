"""Model manager: background preload, atomic swap, failure handling."""

import time
from collections import namedtuple

import pytest

from src.core.defaults import DEFAULTS
from src.core.ladder import Rung
from src.core.model_manager import ModelManager

FAST = {"latency_ms": 1}


def rung(name, model, size, every=1, **opts):
    return Rung(name, model, size, every, backend="fake",
                options={**FAST, **opts})


def make(rungs, failures=None):
    cfg = {"inference": dict(DEFAULTS["inference"]),
           "ladder_settings": dict(DEFAULTS["ladder_settings"])}
    mgr = ModelManager(rungs, cfg,
                       on_failure=lambda i, r: failures.append((i, r))
                       if failures is not None else None)
    mgr.load_initial(0)
    return mgr


def wait_swap(mgr, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        res = mgr.poll()
        if res:
            return res
        time.sleep(0.005)
    return None


RUNGS = [rung("a", "m0", 640), rung("b", "m0", 640, every=2),
         rung("c", "m2", 320, load_ms=80)]


def test_initial_load():
    mgr = make(RUNGS)
    assert mgr.index == 0 and mgr.backend.backend_name == "fake"


def test_shared_model_swap_is_light_and_keeps_backend():
    mgr = make(RUNGS)
    before = mgr.backend
    mgr.request(1)
    res = wait_swap(mgr)
    assert res.light and res.load_s == 0.0
    assert mgr.index == 1 and mgr.backend is before
    assert mgr.rung.detect_every == 2


def test_heavy_swap_preloads_off_thread_then_swaps_instantly():
    mgr = make(RUNGS)
    old = mgr.backend
    mgr.request(2)
    t0 = time.perf_counter()
    assert mgr.poll() is None            # preload still running: no stall
    assert (time.perf_counter() - t0) < 0.02
    res = wait_swap(mgr)
    assert res.idx == 2 and not res.light and res.load_s >= 0.07
    assert res.swap_ms < 5.0             # pointer swap, not a load
    assert mgr.backend is not old and mgr.backend.input_size == 320


def test_old_backend_is_unloaded_after_swap():
    mgr = make(RUNGS)
    old = mgr.backend
    mgr.request(2)
    wait_swap(mgr)
    time.sleep(0.05)
    assert old.vram_mb == 0


def test_failed_load_reports_and_keeps_current():
    failures = []
    bad = rung("bad", "m3", 320, fail_load=True)
    mgr = make([RUNGS[0], bad], failures)
    mgr.request(1)
    time.sleep(0.2)
    assert mgr.poll() is None and mgr.index == 0
    assert failures and failures[0][0] == 1 and "load failed" in failures[0][1]


def test_latest_request_wins():
    mgr = make(RUNGS)
    mgr.request(2)       # slow heavy preload
    time.sleep(0.01)
    mgr.request(1)       # newer, light request supersedes it
    seen = []
    end = time.monotonic() + 1.0
    while time.monotonic() < end:
        res = mgr.poll()
        if res:
            seen.append(res.idx)
        time.sleep(0.01)
    assert seen and seen[-1] == 1 and mgr.index == 1


def test_low_memory_refuses_preload(monkeypatch):
    import src.core.model_manager as mm
    mem = namedtuple("mem", "available")
    monkeypatch.setattr(mm.psutil, "virtual_memory",
                        lambda: mem(available=10 * 1024 * 1024))
    failures = []
    heavy = Rung("h", "m9", 320, backend="onnxruntime")
    mgr = make([RUNGS[0], heavy], failures)
    mgr.request(1)
    time.sleep(0.2)
    assert failures and "low memory" in failures[0][1]
    assert mgr.index == 0


def test_close_unloads_backend():
    mgr = make(RUNGS)
    backend = mgr.backend
    mgr.close()
    assert backend.vram_mb == 0


@pytest.mark.parametrize("idx", [0, 1])
def test_request_current_index_is_noop(idx):
    mgr = make(RUNGS)
    if idx:
        mgr.request(idx)
        wait_swap(mgr)
    mgr.request(idx)
    time.sleep(0.05)
    assert mgr.poll() is None and mgr.index == idx
