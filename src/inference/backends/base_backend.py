"""Abstract base class for all inference backends.

Every backend in SHADE implements this contract. Nothing outside
the backends/ folder imports a backend directly — everything goes
through BackendFactory.
"""

from abc import ABC, abstractmethod

import numpy as np

from src.inference.detection import Detection


class InferenceBackend(ABC):
    """Contract that every inference backend must fulfill."""

    @abstractmethod
    def load(self, model_path: str) -> None:
        """Load a model from disk into memory.

        Args:
            model_path: absolute or project-relative path to the model file.

        Raises:
            FileNotFoundError: if model_path does not exist.
            RuntimeError: if the backend cannot load the model.
        """

    @abstractmethod
    def infer(self, frame: np.ndarray) -> list[Detection]:
        """Run inference on a single BGR frame.

        Args:
            frame: HWC uint8 BGR image (OpenCV format).

        Returns:
            List of Detection objects for this frame.
        """

    @abstractmethod
    def unload(self) -> None:
        """Release all model resources."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Human-readable backend identifier, e.g. 'onnxruntime-cpu'."""

    @property
    @abstractmethod
    def vram_mb(self) -> int:
        """Approximate memory consumed by the loaded model in MB.

        On devices without discrete GPU (e.g. Raspberry Pi), this is
        the system RAM consumed. Named vram_mb so the decision engine
        interface is hardware-agnostic.
        """
