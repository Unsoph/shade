#!/usr/bin/env python3
"""Smoke test — verify inference works with a synthetic frame.

Usage: python scripts/test_smoke.py
"""

import os
import sys
import time

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.inference.backend_factory import create_backend


def main():
    config = {
        "inference": {
            "backend": "onnxruntime",
            "input_size": 640,
            "conf_threshold": 0.25,
            "iou_threshold": 0.45,
            "num_threads": 4,
        }
    }

    model_path = "models/yolov8n.onnx"
    if not os.path.isfile(model_path):
        print(f"ERROR: Model not found at {model_path}")
        sys.exit(1)

    # Create and load backend
    backend = create_backend(config)
    backend.load(model_path)
    print(f"Backend:  {backend.backend_name}")
    print(f"Memory:   {backend.vram_mb} MB")

    # Synthetic frame (640x480 random noise — simulates a real frame)
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Warm up
    _ = backend.infer(frame)

    # Benchmark 10 frames
    times = []
    for i in range(10):
        start = time.monotonic()
        detections = backend.infer(frame)
        elapsed = time.monotonic() - start
        times.append(elapsed)
        print(f"  Frame {i+1}: {elapsed*1000:.1f}ms | {len(detections)} detections")

    avg_ms = sum(times) / len(times) * 1000
    fps = 1000.0 / avg_ms
    print(f"\nAverage:  {avg_ms:.1f}ms per frame")
    print(f"FPS:      {fps:.1f}")
    print(f"Status:   {'PASS' if fps > 1 else 'FAIL'}")

    backend.unload()


if __name__ == "__main__":
    main()
