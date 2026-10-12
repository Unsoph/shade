"""Detection matching for agreement / accuracy checks.

Greedy, class-aware matching by descending confidence. `reference` can be
another model's detections (agreement) or labelled ground truth.
"""

from pathlib import Path

from src.inference.detection import Detection
from src.inference.labels import COCO_LABELS


def iou(a: Detection, b: Detection) -> float:
    ix = max(0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    union = ((a.x2 - a.x1) * (a.y2 - a.y1)
             + (b.x2 - b.x1) * (b.y2 - b.y1) - inter)
    return inter / union if union > 0 else 0.0


def match(preds: list[Detection], refs: list[Detection],
          iou_thr: float = 0.5) -> tuple[int, int, int]:
    """Return (tp, fp, fn) for predictions against references."""
    used: set[int] = set()
    tp = 0
    for p in sorted(preds, key=lambda d: -d.confidence):
        best, best_iou = -1, iou_thr
        for i, r in enumerate(refs):
            if i in used or r.class_id != p.class_id:
                continue
            score = iou(p, r)
            if score >= best_iou:
                best, best_iou = i, score
        if best >= 0:
            used.add(best)
            tp += 1
    return tp, len(preds) - tp, len(refs) - tp


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Precision, recall, F1 (0 when undefined)."""
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def load_yolo_labels(path: Path, width: int, height: int) -> list[Detection]:
    """Read a YOLO-format label file (class cx cy w h, normalised)."""
    out = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        cid = int(parts[0])
        cx, cy, w, h = (float(v) for v in parts[1:5])
        label = COCO_LABELS[cid] if cid < len(COCO_LABELS) else str(cid)
        out.append(Detection(
            int((cx - w / 2) * width), int((cy - h / 2) * height),
            int((cx + w / 2) * width), int((cy + h / 2) * height),
            1.0, cid, label))
    return out
