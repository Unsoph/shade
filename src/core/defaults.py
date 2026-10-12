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
    # Degradation ladder, best first. Rungs whose model file is missing are
    # skipped, so the ladder is whatever is on disk (see scripts/export_models.py).
    "ladder": [
        {"name": "nominal", "model": "models/yolov8n.onnx",
         "input_size": 640, "detect_every": 1},
        {"name": "frame-skip", "model": "models/yolov8n.onnx",
         "input_size": 640, "detect_every": 2},
        {"name": "small-320", "model": "models/yolov8n_320.onnx",
         "input_size": 320, "detect_every": 2},
        {"name": "emergency", "model": "models/yolov8n_320_int8.onnx",
         "input_size": 320, "detect_every": 3},
    ],
    "ladder_settings": {
        "min_free_mb_after_load": 300,  # refuse to preload below this headroom
        "memory_factor": 3.0,           # est. RAM = model file size * factor
        "warmup": True,
        "preload_nice": 10,  # preload thread niceness (Linux); untuned, measure on device
    },
    "input": {
        "enabled": True,
        "frozen_s": 5.0, "frozen_eps": 0.02,
        "dark_level": 8.0, "dark_s": 5.0,
        "lost_s": 3.0, "reopen_cooldown_s": 30.0,
    },
    "runtime": {"max_consecutive_errors": 5},
    "watchdog": {
        "heartbeat_path": "logs/heartbeat.json",
        "heartbeat_interval_s": 0.5,
        "hang_timeout_s": 15.0,      # no heartbeat for this long = hung
        "startup_grace_s": 90.0,     # model load can be slow on an SD card
        "poll_s": 1.0,
        "backoff_initial_s": 2.0,
        "backoff_factor": 2.0,
        "backoff_max_s": 60.0,
        "stable_after_s": 120.0,     # a child this old counts as healthy
        "max_restarts": 8,           # consecutive unstable restarts, then give up
        "kill_timeout_s": 10.0,
        "state_path": "logs/last_known_good.json",
        "lkg_max_age_s": 600.0,      # ignore an older last-known-good rung
        "good_after_s": 60.0,        # stable this long on a rung = known good
    },
    "simulation": {"scenario": "nominal", "speed": 1.0},
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    },
}
