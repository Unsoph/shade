"""Frame sources: file EOF/loop, live reconnect, synthetic camera."""

import numpy as np

from src.core.defaults import DEFAULTS
from src.video.source import FrameSource, is_live
from src.video.synthetic import SyntheticCapture, parse_spec

CAM = {**DEFAULTS["camera"], "reconnect_initial_s": 0.01,
       "reconnect_max_s": 0.05}


class ScriptedCap:
    """Returns `frames` good frames filled with `value`, then fails."""

    def __init__(self, frames, opened=True, value=1):
        self._left, self._opened, self._value = frames, opened, value

    def isOpened(self):
        return self._opened

    def read(self):
        if self._left <= 0:
            return False, None
        self._left -= 1
        return True, np.full((4, 4, 3), self._value, np.uint8)

    def release(self):
        pass


def opener_from(caps):
    it = iter(caps)
    return lambda source: next(it)


def test_parse_spec():
    assert parse_spec("synthetic") == (640, 480, 30.0)
    assert parse_spec("synthetic:320x240@15") == (320, 240, 15.0)
    assert parse_spec("video.mp4") is None


def test_is_live():
    assert is_live(0) and is_live("1") and is_live("synthetic")
    assert is_live("rtsp://cam/stream") and not is_live("video.mp4")


def test_file_source_ends_with_eof():
    src = FrameSource("clip.mp4", CAM, opener=opener_from([ScriptedCap(3)])).start()
    frames = [src.read() for _ in range(3)]
    assert all(f is not None for f in frames)
    assert src.read() is None and src.eof


def test_live_source_reconnects_after_failure():
    events = []
    caps = [ScriptedCap(3), ScriptedCap(0, opened=False),
            ScriptedCap(50, value=200)]
    src = FrameSource(0, CAM, opener=opener_from(caps),
                      on_event=lambda k, d: events.append(k)).start()
    values = []
    for _ in range(200):
        frame = src.read(timeout=0.2)
        if frame is not None:
            values.append(int(frame[0, 0, 0]))
        if 200 in values:
            break
    src.close()
    assert 200 in values, "frames never resumed"
    assert src.reconnects == 1
    assert "camera_open_failed" in events and "camera_reconnect" in events


def test_reconnect_disabled_ends_stream():
    cfg = {**CAM, "reconnect": False}
    src = FrameSource(0, cfg, opener=opener_from([ScriptedCap(2)])).start()
    got = [src.read(timeout=0.3) for _ in range(5)]
    src.close()
    assert src.eof and got[-1] is None


def test_request_reopen_swaps_device():
    caps = [ScriptedCap(10_000, value=10), ScriptedCap(10_000, value=200)]
    src = FrameSource(0, CAM, opener=opener_from(caps)).start()
    assert int(src.read(timeout=1.0)[0, 0, 0]) == 10
    src.request_reopen()
    seen = False
    for _ in range(50):
        frame = src.read(timeout=0.2)
        if frame is not None and int(frame[0, 0, 0]) == 200:
            seen = True
            break
    src.close()
    assert seen and src.reconnects == 1


def test_synthetic_capture_frames_move():
    cap = SyntheticCapture(160, 120, fps=0)
    _, a = cap.read()
    _, b = cap.read()
    assert a.shape == (120, 160, 3) and not np.array_equal(a, b)
