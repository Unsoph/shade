"""Procedural textures for the warehouse (no image assets needed).

Each texture is generated from a seeded RNG and written as a PNG that the
MuJoCo scene references. Colours are BGR because OpenCV writes the files.
"""

import tempfile
from pathlib import Path

import cv2
import numpy as np

SIZE = 256


def _noise(rng, size, scale):
    """Smooth value noise in [-1, 1] at roughly `scale` pixels per feature."""
    cells = max(2, size // scale)
    grid = rng.uniform(-1, 1, (cells, cells)).astype(np.float32)
    return cv2.resize(grid, (size, size), interpolation=cv2.INTER_CUBIC)


def concrete(rng):
    base = 150 + 14 * _noise(rng, SIZE, 64) + 6 * _noise(rng, SIZE, 8)
    base += rng.normal(0, 4, (SIZE, SIZE))
    for _ in range(3):  # stains
        c = rng.integers(0, SIZE, 2)
        cv2.circle(base, (int(c[0]), int(c[1])), int(rng.integers(10, 40)), 128, -1)
    base = cv2.GaussianBlur(base, (5, 5), 0)
    img = np.stack([base * 0.98, base, base * 1.02], -1)
    return np.clip(img, 0, 255).astype(np.uint8)


def cardboard(rng):
    tone = np.array([84, 132, 176], np.float32) * rng.uniform(0.85, 1.1)
    fibre = 10 * _noise(rng, SIZE, 4) + rng.normal(0, 3, (SIZE, SIZE))
    img = tone + fibre[..., None]
    w = SIZE // 7  # packing tape across the middle
    img[SIZE // 2 - w // 2: SIZE // 2 + w // 2] = np.array([120, 175, 205]) + fibre[:w, :, None] / 3
    if rng.random() < 0.7:  # shipping label
        x, y = rng.integers(20, SIZE // 2, 2)
        img[y:y + 40, x:x + 60] = 235
        for k in range(4):
            img[y + 8 + 8 * k: y + 10 + 8 * k, x + 6: x + 50] = 40
    return np.clip(img, 0, 255).astype(np.uint8)


def wood(rng):
    y = np.arange(SIZE, dtype=np.float32)[:, None]
    grain = 14 * np.sin(y / 3 + 6 * _noise(rng, SIZE, 32)) + rng.normal(0, 4, (SIZE, SIZE))
    img = np.array([110, 160, 196], np.float32) + grain[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def blockwall(rng):
    img = np.full((SIZE, SIZE), 196, np.float32) + 6 * _noise(rng, SIZE, 16)
    for r in range(0, SIZE, 32):  # mortar courses, staggered joints
        img[r:r + 2] = 160
        off = 0 if (r // 32) % 2 else 32
        for c in range(off, SIZE, 64):
            img[r:r + 32, c:c + 2] = 160
    img = np.stack([img, img, img * 0.97], -1)
    img[int(SIZE * 0.82):] = (70, 150, 220)  # painted dado band
    return np.clip(img, 0, 255).astype(np.uint8)


def hazard(rng):
    x = np.arange(SIZE)[None, :] + np.arange(SIZE)[:, None]
    stripe = (x // 32) % 2 == 0
    img = np.where(stripe[..., None], np.array([20, 200, 245]), np.array([25, 25, 25]))
    return img.astype(np.uint8)


MAKERS = {"concrete": concrete, "cardboard": cardboard, "wood": wood,
          "wall": blockwall, "hazard": hazard}


def write_textures(rng, folder, variants: int = 4) -> dict[str, list[str]]:
    """Write every texture as PNG into `folder`; returns name -> file paths."""
    folder = Path(folder or tempfile.mkdtemp(prefix="shade_amr_tex_"))
    folder.mkdir(parents=True, exist_ok=True)
    out: dict[str, list[str]] = {}
    for name, make in MAKERS.items():
        n = variants if name == "cardboard" else 1
        out[name] = []
        for i in range(n):
            path = folder / f"{name}{i}.png"
            cv2.imwrite(str(path), make(rng))
            out[name].append(str(path))
    return out
