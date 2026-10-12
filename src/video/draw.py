"""Drawing utilities for rendering detections and HUD on frames."""

import cv2
import numpy as np

from src.inference.detection import Detection

BOX_COLOR = (0, 255, 0)
TEXT_COLOR = (255, 255, 255)
BG_COLOR = (0, 0, 0)
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.5
THICKNESS = 2
STATE_COLORS = {
    "NOMINAL": (0, 200, 0), "ELEVATED": (0, 200, 200),
    "RECOVERING": (200, 200, 0), "DEGRADED": (0, 140, 255),
    "CRITICAL": (0, 0, 255), "POWER_WARNING": (0, 0, 255),
    "OS_CONTENTION": (0, 140, 255), "FAULT": (0, 0, 255),
}


def draw_detections(frame: np.ndarray, detections: list[Detection]) -> None:
    """Draw bounding boxes and labels on the frame in-place."""
    for det in detections:
        cv2.rectangle(frame, (det.x1, det.y1), (det.x2, det.y2), BOX_COLOR, THICKNESS)
        label = f"{det.label} {det.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(label, FONT, FONT_SCALE, 1)
        top = max(th + 8, det.y1)  # keep the label inside the frame
        cv2.rectangle(frame, (det.x1, top - th - 8), (det.x1 + tw + 4, top),
                      BG_COLOR, -1)
        cv2.putText(frame, label, (det.x1 + 2, top - 4), FONT, FONT_SCALE,
                    TEXT_COLOR, 1, cv2.LINE_AA)


def draw_fps(frame: np.ndarray, fps: float) -> None:
    """Draw FPS counter in the top-left corner."""
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30), FONT, 0.8,
                (0, 255, 255), 2, cv2.LINE_AA)


def draw_status(frame: np.ndarray, state: str, rung: str, temp: float) -> None:
    """Draw the controller state, active rung and temperature."""
    color = STATE_COLORS.get(state, TEXT_COLOR)
    cv2.putText(frame, f"{state} | {rung} | {temp:.0f}C", (10, 58), FONT, 0.6,
                color, 2, cv2.LINE_AA)
