"""NMS must be class-aware and use xyxy boxes."""

import numpy as np

from src.inference.nms import iou_one_to_many, nms_per_class


def _boxes(*rows):
    return np.array(rows, dtype=np.float32)


def test_iou_known_value():
    a = np.array([0, 0, 100, 100], dtype=np.float32)
    b = _boxes([60, 0, 160, 100])
    assert abs(iou_one_to_many(a, b)[0] - 0.25) < 1e-6


def test_same_class_overlap_suppressed():
    boxes = _boxes([0, 0, 100, 100], [5, 5, 105, 105])
    keep = nms_per_class(boxes, np.array([0.9, 0.8]), np.array([0, 0]), 0.45)
    assert keep == [0]


def test_different_class_overlap_kept():
    boxes = _boxes([0, 0, 100, 100], [5, 5, 105, 105])
    keep = nms_per_class(boxes, np.array([0.9, 0.8]), np.array([0, 1]), 0.45)
    assert sorted(keep) == [0, 1]


def test_low_overlap_neighbours_both_kept():
    """Regression: xywh/xyxy confusion used to suppress these."""
    boxes = _boxes([0, 0, 100, 100], [60, 0, 160, 100])
    keep = nms_per_class(boxes, np.array([0.9, 0.8]), np.array([0, 0]), 0.45)
    assert sorted(keep) == [0, 1]


def test_empty_input():
    empty = np.zeros((0, 4), dtype=np.float32)
    assert nms_per_class(empty, np.zeros(0), np.zeros(0, dtype=int), 0.5) == []
