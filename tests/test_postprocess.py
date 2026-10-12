"""Pre/postprocessing: colour order, letterbox maths, coordinate mapping."""

import numpy as np

from src.inference.postprocess import letterbox_preprocess, yolov8_postprocess

NUM_CLASSES = 80


def _tensor(dets, n=8400):
    """Build a (1, 84, n) YOLOv8 output with the given (cx,cy,w,h,cls,conf)."""
    out = np.zeros((1, 4 + NUM_CLASSES, n), dtype=np.float32)
    for i, (cx, cy, w, h, cls, conf) in enumerate(dets):
        out[0, :4, i] = (cx, cy, w, h)
        out[0, 4 + cls, i] = conf
    return out


def test_preprocess_converts_bgr_to_rgb():
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    frame[:, :, 0] = 255  # pure blue in BGR
    blob, ratio, pad_w, pad_h = letterbox_preprocess(frame, 640)
    assert blob.shape == (1, 3, 640, 640)
    assert blob[0, 2].max() == 1.0 and blob[0, 0].max() == 0.0  # blue is last
    assert (ratio, pad_w, pad_h) == (1.0, 0, 0)


def test_letterbox_pads_to_square():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    blob, ratio, pad_w, pad_h = letterbox_preprocess(frame, 640)
    assert blob.shape == (1, 3, 640, 640)
    assert ratio == 1.0 and pad_w == 0 and pad_h == 80


def test_postprocess_maps_back_to_original_pixels():
    out = _tensor([(320, 320, 100, 200, 0, 0.9)])
    dets = yolov8_postprocess(out, 1.0, 0, 0)
    assert len(dets) == 1
    d = dets[0]
    assert (d.x1, d.y1, d.x2, d.y2) == (270, 220, 370, 420)
    assert d.label == "person" and abs(d.confidence - 0.9) < 1e-6


def test_postprocess_undoes_letterbox_padding():
    out = _tensor([(320, 400, 100, 100, 2, 0.8)])  # pad_h = 80
    d = yolov8_postprocess(out, 1.0, 0, 80)[0]
    assert (d.y1, d.y2) == (270, 370)
    assert d.label == "car"


def test_boxes_clipped_to_frame():
    out = _tensor([(10, 10, 100, 100, 0, 0.9)])
    d = yolov8_postprocess(out, 1.0, 0, 0, frame_shape=(480, 640))[0]
    assert d.x1 == 0 and d.y1 == 0


def test_below_threshold_dropped():
    out = _tensor([(320, 320, 100, 100, 0, 0.1)])
    assert yolov8_postprocess(out, 1.0, 0, 0, conf_threshold=0.25) == []
