#!/usr/bin/env python3
"""SHADE — Self-Healing Adaptive Deployment Engine.

Entry point: live inference with optional health dashboard.

Usage:
    python run.py                         # USB camera, index 0
    python run.py --source 0              # explicit camera index
    python run.py --source video.mp4      # video file
    python run.py --headless              # no display window
    python run.py --dashboard             # enable health telemetry dashboard
    python run.py --config path/to.yaml   # custom config
"""

import argparse
import logging
import os
import sys

import yaml

from scripts.setup import run_diagnostics
from src.core.config import resolve_path
from src.inference.backend_factory import create_backend


def _load_config(config_path: str) -> dict:
    """Load and return the deployment config."""
    if not os.path.isfile(config_path):
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _setup_logging(config: dict) -> None:
    """Configure logging from deployment config."""
    log_cfg = config.get("logging", {})
    logging.basicConfig(
        level=getattr(logging, log_cfg.get("level", "INFO")),
        format=log_cfg.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="SHADE Inference Engine")
    parser.add_argument("--source", default=None, help="Camera index or video file path")
    parser.add_argument("--config", default="config/deployment.yaml", help="Config file")
    parser.add_argument("--headless", action="store_true", help="Run without display")
    parser.add_argument("--max-frames", type=int, default=0, help="Stop after N frames")
    parser.add_argument("--dashboard", action="store_true", help="Show health dashboard")
    parser.add_argument("--skip-setup", action="store_true", help="Skip diagnostic checks")
    args = parser.parse_args()

    config = _load_config(args.config)
    _setup_logging(config)

    logger = logging.getLogger("shade")

    # Run diagnostics
    if not args.skip_setup:
        if not run_diagnostics():
            sys.exit(1)
        print()

    # Resolve source
    source = args.source
    if source is None:
        source = config.get("camera", {}).get("source", 0)

    display = not args.headless
    if display and config.get("camera", {}).get("display") is False:
        display = False

    max_frames = args.max_frames or config.get("camera", {}).get("max_frames", 0)

    # Create and load backend
    backend = create_backend(config)
    model_path = str(resolve_path(
        config.get("inference", {}).get("model_path", "models/yolov8n.onnx")))

    if not os.path.isfile(model_path):
        logger.error("Model file not found: %s", model_path)
        logger.error("Download YOLOv8n ONNX: https://github.com/ultralytics/assets/releases")
        logger.error("Place it at: %s", model_path)
        sys.exit(1)

    backend.load(model_path)
    logger.info("Backend: %s | Memory: %d MB", backend.backend_name, backend.vram_mb)
    logger.info("Hardware: %s", config.get("device", {}).get("hardware", "unknown"))

    # Health monitoring
    health_monitor = None
    if args.dashboard:
        from src.core.hardware.hw_factory import create_hw_monitor
        from src.core.health_monitor import HealthMonitor
        from src.display.console_dashboard import start_dashboard_thread

        hw_monitor = create_hw_monitor(config)
        health_monitor = HealthMonitor(hw_monitor)
        health_monitor.set_model_info(
            model_name=os.path.basename(model_path),
            backend=backend.backend_name,
            tier=2,  # default tier for yolov8n
            vram=backend.vram_mb,
        )
        health_monitor.start_polling(interval=1.0)
        start_dashboard_thread(health_monitor, refresh_rate=0.5)
        logger.info("Health dashboard started.")

    # Run pipeline
    from src.video.pipeline import run_pipeline
    try:
        run_pipeline(
            backend, source,
            display=display,
            max_frames=max_frames,
            health_monitor=health_monitor,
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        if health_monitor is not None:
            health_monitor.stop_polling()
        backend.unload()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
