"""Detection dataclass — shared across all backends."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Detection:
    """Single object detection result.

    Attributes:
        x1, y1, x2, y2: bounding box in pixel coordinates (original frame)
        confidence: detection confidence score [0, 1]
        class_id: integer class index from the model
        label: human-readable class name (empty string if unavailable)
    """

    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    class_id: int
    label: str = ""
