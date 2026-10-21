import cv2
import numpy as np

from src.core.defaults import DEFAULTS
from src.inference.detection import Detection
from src.video.propagate import BoxShifter
from src.video.scheduler import Scheduler


def cfg(**over):
    return {**DEFAULTS["scheduling"], **over}


def textured(shift=0, size=(240, 320)):
    rng = np.random.default_rng(1)
    base = cv2.GaussianBlur(rng.integers(0, 255, (size[0], size[1] + 80, 3),
                                         dtype=np.uint8), (0, 0), 3)
    return np.ascontiguousarray(base[:, shift:shift + size[1]])


def test_plain_skipping_matches_modulo():
    s = Scheduler(cfg())
    frame = textured()
    picks = []
    for i in range(12):
        run = s.should_detect(frame, 3)
        picks.append(run)
        if run:
            s.after_detect(frame, [])
    assert [i for i, p in enumerate(picks) if p] == [0, 3, 6, 9]


def test_gate_stretches_interval_when_static_only():
    frame = textured()
    s = Scheduler(cfg(gate=True, static_factor=4))
    runs = 0
    for _ in range(40):
        if s.should_detect(frame, 2):
            s.after_detect(frame, [])
            runs += 1
    assert runs <= 40 // 8 + 1          # every 8th frame while static
    moving = Scheduler(cfg(gate=True, static_factor=4))
    runs = 0
    for i in range(40):
        f = textured(shift=(i * 5) % 70)
        if moving.should_detect(f, 2):
            moving.after_detect(f, [])
            runs += 1
    assert runs == 20                    # budget respected, never exceeded


def test_shifter_follows_translation():
    a, b = textured(0), textured(12)     # scene moves 12 px left
    det = Detection(100, 80, 200, 180, 0.9, 0, "x")
    s = BoxShifter()
    s.anchor(a, [det])
    (out,) = s.shift(b)
    assert abs((out.x1 - det.x1) - (-12)) <= 3
    assert out.y1 == det.y1 or abs(out.y1 - det.y1) <= 2


def test_shifter_ignores_uncorrelated_content():
    s = BoxShifter(min_response=0.5)
    det = Detection(100, 80, 200, 180, 0.9, 0, "x")
    s.anchor(textured(0), [det])
    noise = np.random.default_rng(9).integers(0, 255, (240, 320, 3), dtype=np.uint8)
    (out,) = s.shift(noise)
    assert (out.x1, out.y1) == (det.x1, det.y1)


def test_shift_disabled_returns_same_objects():
    s = Scheduler(cfg())
    dets = [Detection(1, 2, 3, 4, 0.5, 0, "x")]
    assert s.on_skip(textured(), dets) is dets
