"""Helpers for running accelerated simulations."""

import copy

TIMER_KEYS = ("poll_interval_s", "dwell_s", "cooldown_s", "recover_hold_s",
              "fps_grace_s", "slope_window_s")


def scale_policy(policy: dict, speed: float) -> dict:
    """Compress policy timers (and slope threshold) for `speed`x scenarios.

    A scenario running `speed` times faster than wall time makes every
    duration look `speed` times longer and every rate `speed` times larger.
    """
    out = copy.deepcopy(policy)
    if speed == 1.0:
        return out
    for key in TIMER_KEYS:
        out[key] = policy[key] / speed
    out["rise_c_per_s"] = policy["rise_c_per_s"] * speed
    return out


# Four-rung ladder on the fake backend: lets a laptop without model files
# exercise swaps. Latency (ms at 640) is a stand-in, not a measurement.
FAKE_LADDER = [
    {"name": "nominal", "model": "fake", "input_size": 640, "detect_every": 1,
     "backend": "fake", "options": {"latency_ms": 60, "load_ms": 300}},
    {"name": "frame-skip", "model": "fake", "input_size": 640,
     "detect_every": 2, "backend": "fake",
     "options": {"latency_ms": 60, "load_ms": 300}},
    {"name": "small-320", "model": "fake-320", "input_size": 320,
     "detect_every": 2, "backend": "fake",
     "options": {"latency_ms": 60, "load_ms": 300}},
    {"name": "emergency", "model": "fake-320-int8", "input_size": 320,
     "detect_every": 3, "backend": "fake",
     "options": {"latency_ms": 40, "load_ms": 300}},
]
