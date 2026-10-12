"""Static INT8 (QDQ) quantization of a YOLOv8 ONNX model with calibration images.

    python scripts/quantize_int8.py --model models/yolov8n_320.onnx \
        --calib path/to/images --out models/yolov8n_320_int8.onnx

Needs a few dozen representative images from the deployment scene. INT8 is
not guaranteed faster on the Pi 5 CPU stack (see docs/DESIGN.md): benchmark
it with scripts/benchmark.py and check accuracy with scripts/eval_agreement.py.
"""

import argparse
import sys
from pathlib import Path

import cv2
from onnxruntime.quantization import (CalibrationDataReader, QuantFormat,
                                      QuantType, quantize_static)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.inference.postprocess import letterbox_preprocess  # noqa: E402

EXT = {".jpg", ".jpeg", ".png", ".bmp"}


class ImageReader(CalibrationDataReader):
    """Feeds letterboxed images exactly as inference preprocesses them."""

    def __init__(self, folder: str, input_name: str, size: int, limit: int):
        paths = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in EXT)
        if not paths:
            raise SystemExit(f"No images found in {folder}")
        self._it = iter(
            {input_name: letterbox_preprocess(cv2.imread(str(p)), size)[0]}
            for p in paths[:limit])

    def get_next(self):
        return next(self._it, None)


def head_nodes(model_path: str) -> list[str]:
    """Names of the Detect-head nodes (the last '/model.N/' scope)."""
    import onnx
    names = [n.name for n in onnx.load(model_path).graph.node]
    scopes = [n.split("/")[1] for n in names if n.startswith("/model.")]
    last = scopes[-1] if scopes else None
    return [n for n in names if last and n.startswith(f"/{last}/")]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--calib", required=True, help="folder of calibration images")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--quantize-head", action="store_true",
                    help="also quantize the Detect head (default keeps it FP32: "
                         "quantizing it zeroed all class scores on yolov8n)")
    args = ap.parse_args(argv)

    import onnxruntime as ort
    meta = ort.InferenceSession(args.model, providers=["CPUExecutionProvider"]
                                ).get_inputs()[0]
    reader = ImageReader(args.calib, meta.name, int(meta.shape[2]), args.limit)
    exclude = [] if args.quantize_head else head_nodes(args.model)
    quantize_static(args.model, args.out, reader, quant_format=QuantFormat.QDQ,
                    activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8,
                    per_channel=True, nodes_to_exclude=exclude)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
