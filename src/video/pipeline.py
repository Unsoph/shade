"""Video capture pipeline — feeds frames to the inference backend.

Auto-detects USB camera vs Pi Camera Module at startup.
Handles camera disconnect gracefully.
"""

import logging
import time
from typing import TYPE_CHECKING

import cv2
import numpy as np

from src.inference.backends.base_backend import InferenceBackend
from src.video.draw import draw_detections, draw_fps

if TYPE_CHECKING:
    from src.core.health_monitor import HealthMonitor

logger = logging.getLogger(__name__)


def _try_picamera2() -> bool:
    """Check if picamera2 is available (Pi Camera Module)."""
    try:
        import picamera2  # noqa: F401
        return True
    except ImportError:
        return False


def _open_camera(source) -> cv2.VideoCapture:
    """Open a video source — camera index, video file path, or picamera2."""
    if isinstance(source, str) and not source.isdigit():
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video file: {source}")
        logger.info("Video source: file %s", source)
        return cap

    cam_index = int(source) if isinstance(source, str) else source
    cap = cv2.VideoCapture(cam_index)
    if cap.isOpened():
        logger.info("Video source: USB camera index %d", cam_index)
        return cap

    if _try_picamera2():
        logger.info("USB camera unavailable, trying picamera2...")
        cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)
        if cap.isOpened():
            logger.info("Video source: Pi Camera via V4L2")
            return cap

    raise RuntimeError(
        f"No camera available at index {cam_index}. "
        "Check USB connection or enable Pi Camera in raspi-config."
    )


def run_pipeline(
    engine: InferenceBackend,
    source,
    display: bool = True,
    max_frames: int = 0,
    health_monitor: "HealthMonitor | None" = None,
) -> None:
    """Main inference loop.

    Args:
        engine: loaded InferenceBackend instance.
        source: camera index (int/str) or video file path.
        display: if True, show OpenCV window. False for headless Pi.
        max_frames: stop after N frames (0 = unlimited).
    """
    cap = _open_camera(source)
    frame_count = 0
    fps = 0.0
    prev_time = time.monotonic()

    logger.info("Pipeline started. Press 'q' to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Frame read failed — end of stream or disconnect.")
                break

            detections = engine.infer(frame)
            frame_count += 1

            # Feed FPS data to health monitor
            if health_monitor is not None:
                health_monitor.fps_tracker.tick()

            now = time.monotonic()
            dt = now - prev_time
            if dt > 0:
                instant_fps = 1.0 / dt
                fps = 0.9 * fps + 0.1 * instant_fps if fps > 0 else instant_fps
            prev_time = now

            if display:
                draw_detections(frame, detections)
                draw_fps(frame, fps)
                try:
                    cv2.imshow("SHADE Inference", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        logger.info("Quit requested by user.")
                        break
                except cv2.error:
                    logger.warning("No GUI support in this OpenCV build; "
                                   "continuing headless.")
                    display = False
            else:
                if frame_count % 30 == 0:
                    logger.info(
                        "Frame %d | FPS %.1f | detections %d",
                        frame_count, fps, len(detections),
                    )

            if max_frames and frame_count >= max_frames:
                logger.info("Reached max_frames=%d, stopping.", max_frames)
                break
    finally:
        cap.release()
        if display:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass
        logger.info(
            "Pipeline stopped after %d frames. Last FPS: %.1f",
            frame_count, fps,
        )
