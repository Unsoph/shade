"""Non-maximum suppression in pure NumPy (class-aware, xyxy boxes).

Replaces cv2.dnn.NMSBoxes, which expects [x, y, w, h] boxes and is not
class-aware. Deterministic and unit-testable without OpenCV.
"""

import numpy as np


def iou_one_to_many(box: np.ndarray, others: np.ndarray) -> np.ndarray:
    """IoU between one xyxy box (4,) and many xyxy boxes (N, 4)."""
    x1 = np.maximum(box[0], others[:, 0])
    y1 = np.maximum(box[1], others[:, 1])
    x2 = np.minimum(box[2], others[:, 2])
    y2 = np.minimum(box[3], others[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (others[:, 2] - others[:, 0]) * (others[:, 3] - others[:, 1])
    union = area + areas - inter
    return np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0)


def nms_per_class(
    boxes: np.ndarray,
    scores: np.ndarray,
    class_ids: np.ndarray,
    iou_threshold: float,
    max_candidates: int = 1000,
) -> list[int]:
    """Return indices kept after class-aware NMS, highest score first.

    Boxes of different classes never suppress each other: each class is
    shifted into its own coordinate range before IoU is computed.
    """
    if len(boxes) == 0:
        return []

    order = np.argsort(-scores)[:max_candidates]
    span = float(boxes.max() - boxes.min()) + 1.0
    shifted = boxes + class_ids[:, None].astype(np.float32) * span

    keep: list[int] = []
    while order.size:
        best = int(order[0])
        keep.append(best)
        if order.size == 1:
            break
        rest = order[1:]
        ious = iou_one_to_many(shifted[best], shifted[rest])
        order = rest[ious <= iou_threshold]
    return keep
