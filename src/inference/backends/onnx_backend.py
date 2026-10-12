"""ONNX Runtime backend — the default backend for Raspberry Pi.

Runs YOLOv8 ONNX models on CPU with a configurable thread count.
Pre/postprocessing lives in the postprocess module.
"""

import logging
import os
import time

import numpy as np
import onnxruntime as ort
import psutil

from src.inference.backends.base_backend import InferenceBackend
from src.inference.detection import Detection
from src.inference.postprocess import letterbox_preprocess, yolov8_postprocess

logger = logging.getLogger(__name__)

SLOW_LOAD_SECONDS = 5.0  # SD-card read suspicion threshold
MB = 1024 * 1024


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
        self._input_name = ""
        self._mem_mb = 0
        self.load_seconds = 0.0

    @property
    def input_size(self) -> int:
        return self._input_size

    def load(self, model_path: str) -> None:
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = self._num_threads
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        rss_before = psutil.Process().memory_info().rss
        start = time.monotonic()
        self._session = ort.InferenceSession(
            model_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self.load_seconds = time.monotonic() - start
        rss_delta = psutil.Process().memory_info().rss - rss_before

        meta = self._session.get_inputs()[0]
        self._input_name = meta.name
        static = meta.shape[2] if isinstance(meta.shape[2], int) else None
        if static and static != self._input_size:
            logger.info("Model input is %d; overriding configured %d.",
                        static, self._input_size)
            self._input_size = static
        # RSS delta is noisy when other threads allocate; never report
        # less than the weights themselves.
        self._mem_mb = max(rss_delta, os.path.getsize(model_path)) // MB

        logger.info("Loaded %s in %.1fs | threads=%d | input=%d | mem~%dMB",
                    model_path, self.load_seconds, self._num_threads,
                    self._input_size, self._mem_mb)
        if self.load_seconds > SLOW_LOAD_SECONDS:
            logger.warning("SD_IO_SLOW: model load took %.1fs", self.load_seconds)

    def infer(self, frame: np.ndarray) -> list[Detection]:
        if self._session is None:
            raise RuntimeError("No model loaded. Call load() first.")
        blob, ratio, pad_w, pad_h = letterbox_preprocess(frame, self._input_size)
        outputs = self._session.run(None, {self._input_name: blob})
        return yolov8_postprocess(
            outputs[0], ratio, pad_w, pad_h,
            self._conf_threshold, self._iou_threshold,
            frame_shape=frame.shape[:2],
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
