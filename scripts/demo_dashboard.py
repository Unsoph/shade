#!/usr/bin/env python3
"""Demo: Health dashboard with simulated inference.

Runs the dashboard with synthetic frames to demonstrate telemetry
without needing a camera or video file.

Usage: python scripts/demo_dashboard.py
"""

import logging
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.hardware.hw_factory import create_hw_monitor
from src.core.health_monitor import HealthMonitor
from src.display.console_dashboard import run_dashboard
from src.inference.backend_factory import create_backend

logging.basicConfig(
    level=logging.WARNING,  # Quiet — let the dashboard speak
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main():
    config = {
        "device": {"hardware": "raspberry_pi"},
        "inference": {
            "backend": "onnxruntime",
            "input_size": 640,
            "conf_threshold": 0.25,
            "iou_threshold": 0.45,
            "num_threads": 4,
        },
    }

    model_path = "models/yolov8n.onnx"
    if not os.path.isfile(model_path):
        print(f"ERROR: Model not found at {model_path}")
        sys.exit(1)

    # Create hardware monitor and health monitor
    hw_monitor = create_hw_monitor(config)
    health_monitor = HealthMonitor(hw_monitor)

    # Load model and set info
    backend = create_backend(config)
    backend.load(model_path)
    health_monitor.set_model_info(
        model_name="yolov8n.onnx",
        backend=backend.backend_name,
        tier=2,
        vram=backend.vram_mb,
    )

    # Start health polling
    health_monitor.start_polling(interval=1.0)

    # Simulate inference in a background thread
    import threading

    def inference_loop():
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        while True:
            backend.infer(frame)
            health_monitor.fps_tracker.tick()

    t = threading.Thread(target=inference_loop, daemon=True)
    t.start()

    # Run dashboard (blocking — Ctrl+C to exit)
    print("Starting SHADE health dashboard... (Ctrl+C to exit)\n")
    try:
        run_dashboard(health_monitor, refresh_rate=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        health_monitor.stop_polling()
        backend.unload()
        print("\nShutdown complete.")


if __name__ == "__main__":
    main()
