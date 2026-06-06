"""Backend factory — the only entry point for creating backends.

Nothing outside backends/ imports a backend class directly.
The factory reads deployment.yaml and returns the correct backend.
"""

import logging

from src.inference.backends.base_backend import InferenceBackend
from src.inference.backends.onnx_backend import ONNXBackend
from src.inference.backends.tflite_backend import TFLiteBackend
from src.inference.backends.openvino_backend import OpenVINOBackend
from src.inference.backends.tensorrt_backend import TensorRTBackend

logger = logging.getLogger(__name__)

_BACKEND_MAP: dict[str, type[InferenceBackend]] = {
    "onnxruntime": ONNXBackend,
    "tflite": TFLiteBackend,
    "openvino": OpenVINOBackend,
    "tensorrt": TensorRTBackend,
}


def create_backend(config: dict) -> InferenceBackend:
    """Create and return an inference backend based on config.

    Args:
        config: parsed deployment.yaml dict. Expected keys:
            - inference.backend: str (e.g. "onnxruntime")
            - inference.input_size: int (e.g. 640)
            - inference.conf_threshold: float
            - inference.iou_threshold: float
            - inference.num_threads: int

    Returns:
        An initialized (but not loaded) InferenceBackend instance.
    """
    inf_cfg = config.get("inference", {})
    backend_name = inf_cfg.get("backend", "onnxruntime")

    if backend_name not in _BACKEND_MAP:
        raise ValueError(
            f"Unknown backend '{backend_name}'. "
            f"Available: {list(_BACKEND_MAP.keys())}"
        )

    backend_cls = _BACKEND_MAP[backend_name]

    # Only ONNXBackend accepts constructor params today.
    # Stubs raise NotImplementedError on load() anyway.
    if backend_cls is ONNXBackend:
        backend = ONNXBackend(
            input_size=inf_cfg.get("input_size", 640),
            conf_threshold=inf_cfg.get("conf_threshold", 0.25),
            iou_threshold=inf_cfg.get("iou_threshold", 0.45),
            num_threads=inf_cfg.get("num_threads", 4),
        )
    else:
        backend = backend_cls()

    logger.info("Backend created: %s", backend.backend_name)
    return backend
