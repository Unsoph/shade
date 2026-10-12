"""Inference loop: frames in, detections out, control plane serviced.

Each iteration is a frame boundary: a preloaded model is swapped in before
inference, never mid-frame. Between detections on frame-skip rungs the
last result is reused.
"""

import logging
import time
from typing import TYPE_CHECKING

import cv2

from src.video.draw import draw_detections, draw_fps, draw_status
from src.video.source import FrameSource

if TYPE_CHECKING:
    from src.app import Runtime

logger = logging.getLogger(__name__)


def _show(frame) -> bool:
    """Show a frame; False once the user presses q. Raises cv2.error on
    OpenCV builds without GUI support."""
    cv2.imshow("SHADE Inference", frame)
    return not (cv2.waitKey(1) & 0xFF == ord("q"))


def run_pipeline(rt: "Runtime", source, display: bool = True,
                 max_frames: int = 0) -> int:
    """Run the loop. Returns the number of frames processed."""
    cfg = rt.config
    manager, health, ih = rt.manager, rt.health, rt.input_health
    src = FrameSource(source, cfg["camera"],
                      on_event=rt.log.record_event).start()
    max_errors = cfg["runtime"]["max_consecutive_errors"]
    reopen_gap = cfg["input"]["reopen_cooldown_s"]
    last_reopen = -reopen_gap
    detections, errors, frames, pending_swap = [], 0, 0, None
    logger.info("Pipeline started%s.", " (press q to quit)" if display else "")

    try:
        while True:
            frame = src.read()
            if frame is None:
                if src.eof:
                    break
                health.set_runtime(input_fault=ih.no_frame())
                continue

            pending_swap = manager.poll() or pending_swap  # frame boundary
            rung = manager.rung
            if frames % rung.detect_every == 0:
                started = time.perf_counter()
                try:
                    detections = manager.backend.infer(frame)
                    errors = 0
                    if pending_swap:  # first inference on the new model
                        rt.controller.on_swap(
                            pending_swap, (time.perf_counter() - started) * 1000)
                        pending_swap = None
                except Exception:  # noqa: BLE001 - count, then escalate
                    errors += 1
                    logger.exception("Inference error %d/%d", errors, max_errors)
                    if errors >= max_errors:
                        raise
            frames += 1

            fault = ih.update(frame) if cfg["input"]["enabled"] else ""
            health.set_runtime(input_fault=fault, detections=len(detections))
            health.fps_tracker.tick()
            now = time.monotonic()
            if fault == "frozen" and src.live and now - last_reopen >= reopen_gap:
                last_reopen = now
                rt.log.record_event("camera_reopen_requested", {"fault": fault})
                src.request_reopen()
            if rt.heartbeat is not None:
                rt.heartbeat.beat(frames)

            if display:
                snap = health.snapshot()
                draw_detections(frame, detections)
                draw_fps(frame, snap.fps)
                draw_status(frame, snap.state, rung.name, snap.cpu_temp)
                try:
                    if not _show(frame):
                        break
                except cv2.error:
                    logger.warning("No GUI in this OpenCV build; headless.")
                    display = False
            elif frames % 30 == 0:
                snap = health.snapshot()
                logger.info("Frame %d | FPS %.1f | %s | rung %s | %d det",
                            frames, snap.fps, snap.state, rung.name,
                            len(detections))
            if max_frames and frames >= max_frames:
                break
    finally:
        src.close()
        if display:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass
        logger.info("Pipeline stopped after %d frames.", frames)
    return frames
