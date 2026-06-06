"""OpenVINO backend stub — optional Pi optimization.

ARM support is limited. Test before committing to this backend.
"""

import numpy as np

from src.inference.backends.base_backend import InferenceBackend
from src.inference.detection import Detection


class OpenVINOBackend(InferenceBackend):
    """OpenVINO backend (not yet implemented)."""

    def load(self, model_path: str) -> None:
        raise NotImplementedError("OpenVINO backend is planned for Stage 5.")

    def infer(self, frame: np.ndarray) -> list[Detection]:
        raise NotImplementedError("OpenVINO backend is planned for Stage 5.")

    def unload(self) -> None:
        raise NotImplementedError("OpenVINO backend is planned for Stage 5.")

    @property
    def backend_name(self) -> str:
        return "openvino-cpu"

    @property
    def vram_mb(self) -> int:
        return 0
