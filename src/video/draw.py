"""Drawing utilities for rendering detections and HUD on frames."""

import cv2
import numpy as np

from src.inference.detection import Detection

# Drawing constants
BOX_COLOR = (0, 255, 0)
TEXT_COLOR = (255, 255, 255)
BG_COLOR = (0, 0, 0)
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.5
THICKNESS = 2


def draw_detections(frame: np.ndarray, detections: list[Detection]) -> None:
    """Draw bounding boxes and labels on the frame in-place."""
    for det in detections:
        cv2.rectangle(frame, (det.x1, det.y1), (det.x2, det.y2), BOX_COLOR, THICKNESS)
        label = f"{det.label} {det.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(label, FONT, FONT_SCALE, 1)
        cv2.rectangle(
            frame,
            (det.x1, det.y1 - th - 8),
            (det.x1 + tw + 4, det.y1),
            BG_COLOR, -1,
        )
        cv2.putText(
            frame, label, (det.x1 + 2, det.y1 - 4),
            FONT, FONT_SCALE, TEXT_COLOR, 1, cv2.LINE_AA,
        )


def draw_fps(frame: np.ndarray, fps: float) -> None:
    """Draw FPS counter in the top-left corner."""
    text = f"FPS: {fps:.1f}"
    cv2.putText(frame, text, (10, 30), FONT, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
