"""TFLite backend stub — placeholder for XNNPACK-accelerated inference.

Will be implemented in Stage 5 when benchmarking ONNX vs TFLite on Pi.
"""

import numpy as np

from src.inference.backends.base_backend import InferenceBackend
from src.inference.detection import Detection


class TFLiteBackend(InferenceBackend):
    """TFLite + XNNPACK backend (not yet implemented)."""

    def load(self, model_path: str) -> None:
        raise NotImplementedError("TFLite backend is planned for Stage 5.")

    def infer(self, frame: np.ndarray) -> list[Detection]:
        raise NotImplementedError("TFLite backend is planned for Stage 5.")

    def unload(self) -> None:
        raise NotImplementedError("TFLite backend is planned for Stage 5.")

    @property
    def backend_name(self) -> str:
        return "tflite-xnnpack"

    @property
    def vram_mb(self) -> int:
        return 0
