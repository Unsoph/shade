"""Built-in defaults merged under config/deployment.yaml.

Keep this the single place where a missing key gets a value, so the rest
of the code can index the config directly.
"""

DEFAULTS: dict = {
    "device": {"hardware": "generic", "name": "shade-dev"},
    "inference": {
        "backend": "onnxruntime",
        "model_path": "models/yolov8n.onnx",
        "input_size": 640,
        "conf_threshold": 0.25,
        "iou_threshold": 0.45,
        "num_threads": 4,
    },
    "camera": {
        "source": 0,
        "display": True,
        "max_frames": 0,
        "reconnect": True,
        "reconnect_initial_s": 1.0,
        "reconnect_max_s": 30.0,
        "loop_video": False,
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    },
}
