"""Regression against the real yolov8n model (skipped when assets are absent).

Put a street photo with people in tests/fixtures/bus.jpg (or set
SHADE_TEST_IMAGE) and models/yolov8n.onnx in place. With Ultralytics'
bus.jpg the model finds 4 persons and 1 bus.
"""

import os
from pathlib import Path

import cv2
import pytest

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "models" / "yolov8n.onnx"
IMAGE = Path(os.environ.get("SHADE_TEST_IMAGE", ROOT / "tests/fixtures/bus.jpg"))

pytestmark = [pytest.mark.realmodel, pytest.mark.skipif(
    not (MODEL.is_file() and IMAGE.is_file()),
    reason="needs models/yolov8n.onnx and a test image")]


def test_detects_people_inside_frame():
    from src.inference.backends.onnx_backend import ONNXBackend
    backend = ONNXBackend(input_size=640)
    backend.load(str(MODEL))
    frame = cv2.imread(str(IMAGE))
    dets = backend.infer(frame)
    h, w = frame.shape[:2]
    assert any(d.label == "person" for d in dets)
    assert all(0 <= d.x1 < d.x2 < w and 0 <= d.y1 < d.y2 < h for d in dets)
    assert all(d.confidence >= 0.25 for d in dets)


def test_small_input_size_runs_on_same_model_path():
    """Static-shape models override the configured size instead of crashing."""
    from src.inference.backends.onnx_backend import ONNXBackend
    backend = ONNXBackend(input_size=320)
    backend.load(str(MODEL))
    assert backend.input_size == 640
