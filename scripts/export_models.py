"""Generate the ladder's ONNX models with Ultralytics (run on your own machine).

    pip install ultralytics onnx
    python scripts/export_models.py            # 640 + 320 FP32 for yolov8n
    python scripts/quantize_int8.py --model models/yolov8n_320.onnx \
        --calib <images> --out models/yolov8n_320_int8.onnx

Static shapes are exported (dynamic=False) because the backend reads the
input size from the model.
"""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--weights", default="yolov8n.pt")
    ap.add_argument("--sizes", default="640,320")
    ap.add_argument("--out-dir", default=str(ROOT / "models"))
    ap.add_argument("--opset", type=int, default=12)
    args = ap.parse_args(argv)

    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics is not installed: pip install ultralytics onnx")
        return 1
    stem = Path(args.weights).stem
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for size in (int(s) for s in args.sizes.split(",")):
        exported = YOLO(args.weights).export(
            format="onnx", imgsz=size, opset=args.opset, dynamic=False,
            simplify=True)
        name = f"{stem}.onnx" if size == 640 else f"{stem}_{size}.onnx"
        shutil.move(exported, out / name)
        print(f"Wrote {out / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
