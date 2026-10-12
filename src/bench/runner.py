"""Benchmark runner: time a rung's backend over a stream of frames."""

import time
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np
import psutil

from src.bench.stats import summarize
from src.core.ladder import Rung
from src.core.swap import build_backend

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp"}


def frame_iter(spec: str) -> Iterator[np.ndarray]:
    """Endless frames from an image, image folder, video, or synthetic."""
    path = Path(spec)
    if spec.startswith("synthetic"):
        from src.video.synthetic import SyntheticCapture, parse_spec
        cap = SyntheticCapture(*(parse_spec(spec)[:2] + (0.0,)))
        while True:
            yield cap.read()[1]
    images = sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_EXT) \
        if path.is_dir() else ([path] if path.suffix.lower() in IMAGE_EXT else [])
    if images:
        frames = [cv2.imread(str(p)) for p in images]
        while True:
            yield from frames
    cap = cv2.VideoCapture(spec)
    while True:
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f"Cannot read frames from {spec}")
        yield frame


def bench_rung(rung: Rung, config: dict, frames: Iterator[np.ndarray],
               n_frames: int, warmup: int = 5) -> dict:
    """Load a rung's model and time `n_frames` end-to-end inferences
    (preprocess + inference + postprocess)."""
    backend = build_backend(rung, config)
    rss0 = psutil.Process().memory_info().rss
    backend.load(rung.model_path())
    for _ in range(warmup):
        backend.infer(next(frames))
    lat = []
    for _ in range(n_frames):
        frame = next(frames)
        t0 = time.perf_counter()
        backend.infer(frame)
        lat.append((time.perf_counter() - t0) * 1000.0)
    rss_mb = (psutil.Process().memory_info().rss - rss0) / (1024 * 1024)
    backend.unload()
    return {"rung": rung.name, "model": rung.model, "input": rung.input_size,
            "threads": rung.threads, "detect_every": rung.detect_every,
            "rss_delta_mb": round(rss_mb, 1),
            **summarize(lat, rung.detect_every)}
