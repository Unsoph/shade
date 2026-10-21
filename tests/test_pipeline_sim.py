"""End-to-end: simulated thermal spike drives real swaps on fake backends."""

import copy

from src.app import build_runtime, run
from src.core.defaults import DEFAULTS

LADDER = [
    {"name": f"r{i}", "model": f"fake-{size}", "input_size": size,
     "detect_every": every, "backend": "fake",
     "options": {"latency_ms": 2, "load_ms": 20}}
    for i, (size, every) in enumerate([(640, 1), (640, 2), (320, 2), (320, 3)])
]


def config(scenario="thermal_spike", speed=25.0):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["device"]["hardware"] = "simulated"
    cfg["simulation"] = {"scenario": scenario, "speed": speed}
    cfg["ladder"] = LADDER
    cfg["ladder_settings"]["warmup"] = False
    cfg["watchdog"]["state_path"] = ""  # never touch the real state file
    return cfg


def test_spike_degrades_then_recovers_with_audit_trail():
    rt = build_runtime(config(), db_path=":memory:")
    frames = run(rt, "synthetic:160x120@150", display=False,
                 max_frames=1200, close=False)
    decisions = list(reversed(rt.log.recent(100, kind="decision")))
    assert frames == 1200
    downs = [d for d in decisions if d["action"] == "degrade"]
    assert max(d["to_rung"] for d in downs) == 3
    assert any("critical" in " ".join(d["reasons"]) for d in downs)
    ups = [d for d in decisions if d["action"] == "upgrade"]
    assert ups and ups[-1]["to_rung"] == 0
    assert all(d["from_rung"] - d["to_rung"] == 1 for d in ups)  # one step each
    rt.close()


def test_every_decision_has_a_matching_swap_record():
    rt = build_runtime(config(), db_path=":memory:")
    run(rt, "synthetic:160x120@150", display=False, max_frames=1200, close=False)
    moves = rt.log.count("decision")
    swaps = rt.log.recent(100, kind="swap_done")
    assert swaps and all(s["detail"]["swap_ms"] < 5.0 for s in swaps)
    assert len(swaps) >= 3 and moves >= len(swaps)
    rt.close()


def test_no_frame_gaps_during_heavy_swap():
    """The preload must not stall the inference loop."""
    import time
    from src.core.model_manager import ModelManager  # noqa: F401
    rt = build_runtime(config("nominal"), db_path=":memory:")
    stamps = []
    orig = rt.health.fps_tracker.tick
    rt.health.fps_tracker.tick = lambda: (stamps.append(time.monotonic()), orig())
    rt.manager.request(3)  # 20 ms background load while frames flow
    run(rt, "synthetic:160x120@150", display=False, max_frames=120, close=False)
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert max(gaps) < 0.1  # no gap anywhere near a model load + frames
    assert rt.log.count("swap_done") == 1
    rt.close()


def test_scheduler_gate_reduces_detector_calls_in_pipeline():
    cfg = config("nominal")
    cfg["ladder"] = LADDER[:1]
    cfg["scheduling"].update(gate=True, motion_threshold=1e9, static_factor=4)
    rt = build_runtime(cfg, db_path=":memory:")
    run(rt, "synthetic:160x120@300", display=False, max_frames=80, close=False)
    assert 15 <= rt.manager.backend.calls <= 21  # ~ 80 / 4, plus the first
    rt.close()
