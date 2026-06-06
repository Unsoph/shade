"""ONNX Runtime backend — the default backend for Raspberry Pi.

Runs YOLOv8 ONNX models on CPU with configurable thread count.
Delegates preprocessing and postprocessing to postprocess module.
"""

import logging
import os
import time

import numpy as np
import onnxruntime as ort

from src.inference.backends.base_backend import InferenceBackend
from src.inference.detection import Detection
from src.inference.postprocess import letterbox_preprocess, yolov8_postprocess

logger = logging.getLogger(__name__)


class ONNXBackend(InferenceBackend):
    """ONNX Runtime CPU backend for YOLOv8 models."""

    def __init__(
        self,
        input_size: int = 640,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        num_threads: int = 4,
    ):
        self._input_size = input_size
        self._conf_threshold = conf_threshold
        self._iou_threshold = iou_threshold
        self._num_threads = num_threads
        self._session: ort.InferenceSession | None = None
        self._input_name: str = ""
        self._model_path: str = ""
        self._mem_mb: int = 0

    def load(self, model_path: str) -> None:
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = self._num_threads
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        start = time.monotonic()
        self._session = ort.InferenceSession(
            model_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        elapsed = time.monotonic() - start

        self._input_name = self._session.get_inputs()[0].name
        self._model_path = model_path
        self._mem_mb = os.path.getsize(model_path) // (1024 * 1024)

        logger.info(
            "Loaded %s in %.1fs | threads=%d | size=%dMB",
            model_path, elapsed, self._num_threads, self._mem_mb,
        )
        if elapsed > 5.0:
            logger.warning("SD_IO_SLOW: model load took %.1fs (>5s)", elapsed)

    def infer(self, frame: np.ndarray) -> list[Detection]:
        if self._session is None:
            raise RuntimeError("No model loaded. Call load() first.")

        img, ratio, pad_w, pad_h = letterbox_preprocess(frame, self._input_size)
        outputs = self._session.run(None, {self._input_name: img})
        return yolov8_postprocess(
            outputs[0], ratio, pad_w, pad_h,
            self._conf_threshold, self._iou_threshold,
        )

    def unload(self) -> None:
        self._session = None
        self._mem_mb = 0
        logger.info("ONNX model unloaded.")

    @property
    def backend_name(self) -> str:
        return "onnxruntime-cpu"

    @property
    def vram_mb(self) -> int:
        return self._mem_mb
