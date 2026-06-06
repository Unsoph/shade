"""TensorRT backend stub — exists so the registry knows about it.

Will be implemented when migrating to Jetson hardware.
No TensorRT imports — not even try/except.
"""

import numpy as np

from src.inference.backends.base_backend import InferenceBackend
from src.inference.detection import Detection


class TensorRTBackend(InferenceBackend):
    """TensorRT backend (Jetson only, not implemented)."""

    def load(self, model_path: str) -> None:
        raise NotImplementedError(
            "TensorRT backend requires Jetson hardware. "
            "Use onnxruntime or tflite on Raspberry Pi."
        )

    def infer(self, frame: np.ndarray) -> list[Detection]:
        raise NotImplementedError("TensorRT backend requires Jetson hardware.")

    def unload(self) -> None:
        raise NotImplementedError("TensorRT backend requires Jetson hardware.")

    @property
    def backend_name(self) -> str:
        return "tensorrt"

    @property
    def vram_mb(self) -> int:
        return 0
