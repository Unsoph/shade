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
    "policy": {
        "poll_interval_s": 1.0,
        # temperature bands (deg C); Pi 5 starts soft-throttling near 80
        "warm_c": 70.0,
        "degrade_c": 75.0,
        "critical_c": 80.0,
        "upgrade_gate_c": 65.0,
        # anticipation: rising this fast while warm escalates one level
        "rise_c_per_s": 0.5,
        "slope_window_s": 10.0,
        "mem_warn_pct": 85.0,
        "mem_crit_pct": 92.0,
        "swap_warn_pct": 10.0,
        "swap_crit_pct": 30.0,
        "min_fps": 0.0,  # 0 disables the FPS-based signal
        "fps_grace_s": 15.0,  # ignore FPS this long after any rung change
        # anti-flapping guards
        "confirm_samples": 3,
        "dwell_s": 10.0,
        "cooldown_s": 20.0,
        "recover_hold_s": 30.0,
        # pressure level (0..3) -> minimum degradation rung
        "level_to_rung": [0, 1, 2, 3],
        "db_path": "logs/shade.db",
    },
    "simulation": {"scenario": "nominal", "speed": 1.0},
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    },
}
