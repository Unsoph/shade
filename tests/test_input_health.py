"""Input health: frozen / dark / lost detection with an injected clock."""

import numpy as np

from src.core.defaults import DEFAULTS
from src.core.input_health import InputHealth

CFG = DEFAULTS["input"]


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make():
    clk = Clock()
    return clk, InputHealth(CFG, clk)


def frame(value=128, noise_seed=None):
    f = np.full((48, 64, 3), value, np.uint8)
    if noise_seed is not None:
        rng = np.random.default_rng(noise_seed)
        f = np.clip(f + rng.integers(-40, 40, f.shape), 0, 255).astype(np.uint8)
    return f


def test_moving_feed_is_healthy():
    clk, ih = make()
    for i in range(20):
        clk.t = i
        assert ih.update(frame(noise_seed=i)) == ""


def test_identical_frames_become_frozen_after_threshold():
    clk, ih = make()
    result = []
    for i in range(10):
        clk.t = i
        result.append(ih.update(frame()))
    assert result[:5] == [""] * 5          # frozen_s = 5
    assert result[-1] == "frozen"


def test_recovers_when_frames_change_again():
    clk, ih = make()
    for i in range(8):
        clk.t = i
        ih.update(frame())
    clk.t = 9
    assert ih.update(frame(noise_seed=3)) == ""


def test_dark_feed_detected():
    clk, ih = make()
    out = ""
    for i in range(8):
        clk.t = i
        out = ih.update(frame(value=2, noise_seed=i + 100) // 20)
    assert out == "dark"


def test_lost_feed():
    clk, ih = make()
    ih.update(frame())
    clk.t = 1
    assert ih.no_frame() == ""
    clk.t = 4
    assert ih.no_frame() == "lost"
