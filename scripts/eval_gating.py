"""Accuracy vs detector calls for frame skipping, gating and box shifting.

    python scripts/eval_gating.py --image photo.jpg [--every 2,4,6]

Builds a panning video from one still image (static, slow pan, static, fast
pan), runs the real detector on every frame once as the reference, then
replays each scheduling arm and scores its output against that reference
(F1 at IoU 0.5). Calls = share of frames that ran the detector.

LIMITS: the camera motion is a global pan of a still scene, which suits the
shifter; objects moving on their own are not covered. Use a real video for
claims (--video), and a Pi for timing.
"""

import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bench.matching import match, prf  # noqa: E402
from src.core.defaults import DEFAULTS  # noqa: E402
from src.inference.backends.onnx_backend import ONNXBackend  # noqa: E402
from src.video.scheduler import Scheduler  # noqa: E402

PHASES = [("static", 60, 0), ("slow-pan", 120, 2), ("static", 60, 0),
          ("fast-pan", 120, 8)]
ARMS = {"hold": (False, False), "shift": (False, True),
        "gate": (True, False), "gate+shift": (True, True)}


def pan_frames(image, win_w: int):
    h, w = image.shape[:2]
    span, pos, direction = w - win_w, 0, 1
    for phase, n, speed in PHASES:
        for _ in range(n):
            pos += direction * speed
            if not 0 <= pos <= span:
                direction, pos = -direction, max(0, min(span, pos))
            yield phase, image[:, pos:pos + win_w].copy()


def load_video(path: str):
    cap = cv2.VideoCapture(path)
    while True:
        ok, frame = cap.read()
        if not ok:
            return
        yield "video", frame


def replay(frames, cache, every, gate, shift, scfg):
    sched = Scheduler({**scfg, "gate": gate, "shift": shift})
    dets, outputs = [], []
    for i, (_, frame) in enumerate(frames):
        if sched.should_detect(frame, every):
            dets = cache[i]
            sched.after_detect(frame, dets)
        else:
            dets = sched.on_skip(frame, dets)
        outputs.append(dets)
    return outputs, sched.detections_run / len(frames)


def f1(outputs, cache, labels, phase=None, iou=0.5):
    tp = fp = fn = 0
    for out, ref, lab in zip(outputs, cache, labels):
        if phase and not lab.startswith(phase):
            continue
        a, b, c = match(out, ref, iou)
        tp, fp, fn = tp + a, fp + b, fn + c
    return prf(tp, fp, fn)[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--image", default="")
    ap.add_argument("--video", default="")
    ap.add_argument("--model", default="models/yolov8n.onnx")
    ap.add_argument("--every", default="2,4")
    ap.add_argument("--iou", default="0.5,0.75", help="match thresholds")
    args = ap.parse_args(argv)
    if bool(args.image) == bool(args.video):
        ap.error("give exactly one of --image / --video")
    if args.image:
        img = cv2.imread(args.image)
        frames = list(pan_frames(img, int(img.shape[1] * 0.6)))
    else:
        frames = list(load_video(args.video))
    backend = ONNXBackend(input_size=640)
    backend.load(args.model)
    cache = [backend.infer(f) for _, f in frames]  # per-frame reference
    labels = [lab for lab, _ in frames]
    scfg = DEFAULTS["scheduling"]
    print(f"{len(frames)} frames; reference = detector on every frame")
    print(f"{'IoU':>5s} {'every':>5s} {'arm':12s} {'calls':>7s} {'F1 all':>8s} "
          f"{'static':>8s} {'slow':>8s} {'fast':>8s}")
    for iou in (float(v) for v in args.iou.split(",")):
        for every in (int(e) for e in args.every.split(",")):
            for arm, (gate, shift) in ARMS.items():
                out, calls = replay(frames, cache, every, gate, shift, scfg)
                cols = [f1(out, cache, labels, p, iou)
                        for p in (None, "static", "slow", "fast")]
                print(f"{iou:5.2f} {every:5d} {arm:12s} {calls:7.2f} " +
                      " ".join(f"{c:8.3f}" for c in cols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
