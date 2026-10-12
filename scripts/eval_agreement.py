"""Measure how much a cheaper rung's detections agree with a reference.

    python scripts/eval_agreement.py --images DIR [--labels DIR]

Without --labels, the first rung (best model) is the reference and every
other rung is scored against it ("agreement", not accuracy). With YOLO-format
--labels, every rung is scored against ground truth. Either way the numbers
come from your images; nothing is assumed.
"""

import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bench.matching import load_yolo_labels, match, prf  # noqa: E402
from src.bench.runner import IMAGE_EXT  # noqa: E402
from src.core.config import load_config  # noqa: E402
from src.core.ladder import available_rungs, parse_ladder  # noqa: E402
from src.core.swap import build_backend  # noqa: E402


def detections_for(rung, config, images):
    backend = build_backend(rung, config)
    backend.load(rung.model_path())
    out = [backend.infer(im) for im in images]
    backend.unload()
    return out


def score(preds, refs, iou_thr):
    tp = fp = fn = 0
    for p, r in zip(preds, refs):
        a, b, c = match(p, r, iou_thr)
        tp, fp, fn = tp + a, fp + b, fn + c
    return prf(tp, fp, fn)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="config/deployment.yaml")
    ap.add_argument("--images", required=True)
    ap.add_argument("--labels", default="")
    ap.add_argument("--iou", type=float, default=0.5)
    args = ap.parse_args(argv)

    config = load_config(args.config)
    paths = sorted(p for p in Path(args.images).iterdir()
                   if p.suffix.lower() in IMAGE_EXT)
    images = [cv2.imread(str(p)) for p in paths]
    rungs = available_rungs(parse_ladder(config))
    if not images or not rungs:
        print("Need images and at least one available rung.")
        return 1
    if args.labels:
        refs = [load_yolo_labels(Path(args.labels) / f"{p.stem}.txt",
                             im.shape[1], im.shape[0])
                for p, im in zip(paths, images)]
        scored, kind = rungs, "ground truth"
    else:
        refs = detections_for(rungs[0], config, images)
        scored, kind = rungs[1:], f"reference rung '{rungs[0].name}'"
    print(f"Scoring against {kind} on {len(images)} images, IoU>={args.iou}")
    for rung in scored:
        p, r, f1 = score(detections_for(rung, config, images), refs, args.iou)
        print(f"{rung.name:12s} precision={p:.3f} recall={r:.3f} f1={f1:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
