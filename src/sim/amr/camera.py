"""Onboard camera: renders what the robot sees as a BGR frame (OpenCV layout).

Mounted on the chassis at `mount_m` (forward, left, up) and pitched by
`pitch_deg`; it moves and turns with the base. Uses PyBullet's software
renderer so it works headless.
"""

import math

import numpy as np
import pybullet as p


class Camera:
    def __init__(self, cid: int, cfg: dict):
        self.cid, self.c = cid, cfg
        self.w, self.h = cfg["width"], cfg["height"]
        self.proj = p.computeProjectionMatrixFOV(cfg["fov_deg"], self.w / self.h,
                                                 cfg["near_m"], cfg["far_m"])
        pitch = math.radians(cfg["pitch_deg"])
        self._fwd = np.array([math.cos(pitch), 0.0, math.sin(pitch)])
        self._mount = np.array(cfg["mount_m"], dtype=float)

    def view(self, pos, orn):
        rot = np.array(p.getMatrixFromQuaternion(orn)).reshape(3, 3)
        eye = np.asarray(pos) + rot @ self._mount
        target = eye + rot @ self._fwd
        up = rot @ np.array([0.0, 0.0, 1.0])
        return p.computeViewMatrix(eye.tolist(), target.tolist(), up.tolist())

    def capture(self, pos, orn) -> np.ndarray:
        """Render one frame from the robot pose; returns HxWx3 uint8 BGR."""
        _, _, rgba, _, _ = p.getCameraImage(
            self.w, self.h, self.view(pos, orn), self.proj,
            renderer=p.ER_TINY_RENDERER, physicsClientId=self.cid)
        img = np.asarray(rgba, dtype=np.uint8).reshape(self.h, self.w, 4)
        return np.ascontiguousarray(img[:, :, 2::-1])
