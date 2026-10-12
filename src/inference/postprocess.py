"""YOLOv8 pre/postprocessing shared by all backends.

Preprocess: BGR frame -> letterboxed RGB float blob (what YOLOv8 expects).
Postprocess: raw (1, 4+C, N) tensor -> class-aware NMS -> Detection list.
"""

import cv2
import numpy as np

from src.inference.detection import Detection
from src.inference.labels import COCO_LABELS
from src.inference.nms import nms_per_class

__all__ = ["COCO_LABELS", "letterbox_preprocess", "yolov8_postprocess"]

PAD_VALUE = 114  # Ultralytics letterbox gray


def letterbox_preprocess(frame: np.ndarray, input_size: int):
    """Letterbox resize, BGR->RGB, normalize, HWC->CHW, add batch dim.

    Returns:
        (blob, ratio, pad_w, pad_h)
    """
    h, w = frame.shape[:2]
    ratio = min(input_size / h, input_size / w)
    new_w, new_h = int(round(w * ratio)), int(round(h * ratio))
    pad_w, pad_h = (input_size - new_w) // 2, (input_size - new_h) // 2

    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((input_size, input_size, 3), PAD_VALUE, dtype=np.uint8)
    canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized

    rgb = canvas[:, :, ::-1]
    blob = np.ascontiguousarray(rgb, dtype=np.float32) / 255.0
    return blob.transpose(2, 0, 1)[np.newaxis], ratio, pad_w, pad_h


def yolov8_postprocess(
    output: np.ndarray,
    ratio: float,
    pad_w: int,
    pad_h: int,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    frame_shape: tuple[int, int] | None = None,
) -> list[Detection]:
    """YOLOv8 output (1, 4+C, N) -> list[Detection] in original pixels.

    Args:
        frame_shape: (height, width) of the source frame; boxes are clipped
            to it when given.
    """
    preds = output[0]
    if preds.shape[0] < preds.shape[1]:  # (4+C, N) -> (N, 4+C)
        preds = preds.T

    boxes_xywh, scores = preds[:, :4], preds[:, 4:]
    class_ids = scores.argmax(axis=1)
    confidences = scores[np.arange(len(scores)), class_ids]

    mask = confidences >= conf_threshold
    if not mask.any():
        return []
    boxes_xywh, confidences, class_ids = (
        boxes_xywh[mask], confidences[mask], class_ids[mask],
    )

    cx, cy, w, h = boxes_xywh.T
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
    keep = nms_per_class(boxes, confidences, class_ids, iou_threshold)

    out: list[Detection] = []
    for i in keep:
        x1, y1, x2, y2 = boxes[i]
        x1, x2 = (x1 - pad_w) / ratio, (x2 - pad_w) / ratio
        y1, y2 = (y1 - pad_h) / ratio, (y2 - pad_h) / ratio
        if frame_shape is not None:
            fh, fw = frame_shape
            x1, x2 = np.clip([x1, x2], 0, fw - 1)
            y1, y2 = np.clip([y1, y2], 0, fh - 1)
        cid = int(class_ids[i])
        label = COCO_LABELS[cid] if cid < len(COCO_LABELS) else str(cid)
        out.append(Detection(
            int(x1), int(y1), int(x2), int(y2),
            float(confidences[i]), cid, label,
        ))
    return out
