"""Helpers for running accelerated simulations."""

import copy

TIMER_KEYS = ("dwell_s", "cooldown_s", "recover_hold_s", "fps_grace_s",
              "slope_window_s")


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
