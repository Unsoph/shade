"""YOLOv8 postprocessing utilities — shared across backends.

Handles output parsing, NMS, and coordinate unscaling.
"""

import cv2
import numpy as np

from src.inference.detection import Detection

# COCO class names — YOLOv8 default (80 classes)
COCO_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
]


def letterbox_preprocess(frame: np.ndarray, input_size: int):
    """Letterbox resize, normalize, HWC→CHW, add batch dim.

    Returns:
        (blob, ratio, pad_w, pad_h)
    """
    h, w = frame.shape[:2]
    ratio = min(input_size / h, input_size / w)
    new_w, new_h = int(w * ratio), int(h * ratio)
    pad_w, pad_h = (input_size - new_w) // 2, (input_size - new_h) // 2

    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((input_size, input_size, 3), 114, dtype=np.uint8)
    canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized

    blob = canvas.astype(np.float32) / 255.0
    blob = blob.transpose(2, 0, 1)[np.newaxis]  # BCHW
    return blob, ratio, pad_w, pad_h


def yolov8_postprocess(
    output: np.ndarray,
    ratio: float,
    pad_w: int,
    pad_h: int,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
) -> list[Detection]:
    """YOLOv8 output: (1, 84, 8400) → list[Detection]."""
    preds = output[0].T  # (8400, 84)
    boxes_xywh = preds[:, :4]
    scores = preds[:, 4:]

    class_ids = scores.argmax(axis=1)
    confidences = scores[np.arange(len(scores)), class_ids]

    mask = confidences >= conf_threshold
    boxes_xywh = boxes_xywh[mask]
    confidences = confidences[mask]
    class_ids = class_ids[mask]

    if len(boxes_xywh) == 0:
        return []

    # xywh → xyxy
    x, y, w, h = boxes_xywh.T
    x1 = x - w / 2
    y1 = y - h / 2
    x2 = x + w / 2
    y2 = y + h / 2
    boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

    # NMS
    indices = cv2.dnn.NMSBoxes(
        boxes_xyxy.tolist(), confidences.tolist(),
        conf_threshold, iou_threshold,
    )
    if len(indices) == 0:
        return []

    indices = indices.flatten()
    detections = []
    for i in indices:
        bx1, by1, bx2, by2 = boxes_xyxy[i]
        bx1 = int((bx1 - pad_w) / ratio)
        by1 = int((by1 - pad_h) / ratio)
        bx2 = int((bx2 - pad_w) / ratio)
        by2 = int((by2 - pad_h) / ratio)
        cid = int(class_ids[i])
        label = COCO_LABELS[cid] if cid < len(COCO_LABELS) else str(cid)
        detections.append(
            Detection(bx1, by1, bx2, by2, float(confidences[i]), cid, label)
        )

    return detections
