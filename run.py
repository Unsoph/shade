#!/usr/bin/env python3
"""SHADE — Self-Healing Adaptive Deployment Engine.

Usage:
    python run.py                              # USB camera 0
    python run.py --source video.mp4           # video file
    python run.py --headless --dashboard       # terminal telemetry only
    python run.py --fake --simulate thermal_ramp --speed 10 \\
        --source synthetic --headless          # laptop demo, no model/Pi
"""

import argparse
import logging
import signal
import sys

from src.app import build_runtime, run
from src.core.config import load_config, setup_logging


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="SHADE inference engine")
    ap.add_argument("--source", default=None,
                    help="camera index, video path/URL, or synthetic[:WxH@fps]")
    ap.add_argument("--config", default="config/deployment.yaml")
    ap.add_argument("--headless", action="store_true", help="no display window")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--dashboard", action="store_true", help="terminal dashboard")
    ap.add_argument("--skip-setup", action="store_true", help="skip diagnostics")
    ap.add_argument("--simulate", metavar="SCENARIO", default=None,
                    help="replay a hardware scenario (see src/core/hardware/scenarios.py)")
    ap.add_argument("--speed", type=float, default=None,
                    help="scenario time compression for --simulate")
    ap.add_argument("--fake", action="store_true",
                    help="fake backends: no model files needed")
    ap.add_argument("--start-rung", default="0",
                    help="rung name or index; -1 = emergency rung")
    ap.add_argument("--db", default=None, help="decision log path")
    ap.add_argument("--supervised", action="store_true",
                    help="run under the watchdog supervisor (auto-restart)")
    ap.add_argument("--serve", nargs="?", const=-1, type=int, metavar="PORT",
                    help="serve /metrics, /status and a live page (default port "
                         "from config observability.port)")
    ap.add_argument("--serve-host", default=None, metavar="HOST",
                    help="bind address for --serve (default 127.0.0.1; the "
                         "server is unauthenticated)")
    ap.add_argument("--heartbeat", default=None, help=argparse.SUPPRESS)
    return ap.parse_args(argv)


def _on_sigterm(*_) -> None:
    raise KeyboardInterrupt


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1
    setup_logging(config)
    logger = logging.getLogger("shade")

    if args.supervised:
        from src.watchdog.launcher import supervise
        return supervise(config, argv if argv is not None else sys.argv[1:])

    if args.simulate:
        config["device"]["hardware"] = "simulated"
        config["simulation"]["scenario"] = args.simulate
        if args.speed:
            config["simulation"]["speed"] = args.speed
    if not args.skip_setup and not args.fake:
        from scripts.setup import run_diagnostics
        if not run_diagnostics():
            return 1
        print()

    if args.serve is not None:
        config["observability"]["enabled"] = True
        if args.serve >= 0:
            config["observability"]["port"] = args.serve
    if args.serve_host:
        config["observability"]["host"] = args.serve_host

    source = args.source if args.source is not None else config["camera"]["source"]
    display = not args.headless and config["camera"]["display"]
    max_frames = args.max_frames or config["camera"]["max_frames"]
    try:
        rt = build_runtime(config, args.start_rung, args.fake, args.db,
                           args.heartbeat)
    except (RuntimeError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    # The supervisor stops us with SIGTERM: shut down cleanly.
    signal.signal(signal.SIGTERM, _on_sigterm)
    run(rt, source, display, max_frames, args.dashboard)
    return 0


if __name__ == "__main__":
    sys.exit(main())
