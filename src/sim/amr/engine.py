"""MuJoCo engine for the AMR twin: build the scene, drive the robot, animate
workers, and render the onboard (or chase) camera as BGR frames.

Headless Linux renders through EGL (software or GPU); macOS uses its native
OpenGL. Hidden collision boxes (geom group 3) are excluded from renders.
"""

import math
import os
import sys

if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("MUJOCO_GL", "egl")

import mujoco  # noqa: E402
import numpy as np  # noqa: E402

from src.sim.amr.scene import build_scene  # noqa: E402


class MjEngine:
    def __init__(self, cfg: dict, rngs: dict, start_pose, tex_dir=None):
        self.cfg = cfg
        xml, self.workers, self.meta = build_scene(cfg, rngs, start_pose, tex_dir)
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(self.model)
        m = self.model
        jid = lambda n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)  # noqa: E731
        root = jid("amr_root")
        self._qpos, self._qvel = m.jnt_qposadr[root], m.jnt_dofadr[root]
        self._wheel_dofs = [m.jnt_dofadr[jid(f"wheel_{s}")] for s in ("left", "right")]
        body = lambda n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, n)  # noqa: E731
        self.mass_kg = float(m.body_subtreemass[body("amr")])
        self._mocap = {}
        for w in self.workers:
            for name in ("torso", "leg_l", "leg_r", "arm_l", "arm_r"):
                self._mocap[(w.i, name)] = m.body_mocapid[body(f"w{w.i}_{name}")]
        r = cfg["render"]
        self.renderer = mujoco.Renderer(m, r["height"], r["width"])
        self._snap = None
        self.opt = mujoco.MjvOption()
        self.opt.geomgroup[3] = 0
        self.move_people(0.0)
        mujoco.mj_forward(m, self.data)

    def close(self) -> None:
        for r in (self.renderer, self._snap):
            if r is not None:
                r.close()

    def command(self, v: float, w: float) -> None:
        c = self.cfg["robot"]
        half, r = c["track_m"] / 2, c["wheel_radius_m"]
        self.data.ctrl[0] = (v - w * half) / r
        self.data.ctrl[1] = (v + w * half) / r

    def step(self, n: int = 1) -> None:
        mujoco.mj_step(self.model, self.data, nstep=n)

    def pose(self) -> tuple[float, float, float]:
        x, y, _, qw, qx, qy, qz = self.data.qpos[self._qpos:self._qpos + 7]
        return float(x), float(y), math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))

    def speed(self) -> float:
        vx, vy = self.data.qvel[self._qvel:self._qvel + 2]
        return float(math.hypot(vx, vy))

    def wheel_power_w(self) -> float:
        force = self.data.actuator_force
        return float(sum(max(force[k] * self.data.qvel[d], 0.0)
                         for k, d in enumerate(self._wheel_dofs)))

    def move_people(self, dt: float) -> None:
        for w in self.workers:
            for name, pos, quat in w.poses(w.step(dt)):
                mid = self._mocap[(w.i, name)]
                self.data.mocap_pos[mid] = pos
                self.data.mocap_quat[mid] = quat

    def render(self, camera: str = "onboard", snapshot: bool = False) -> np.ndarray:
        """Render a camera; returns HxWx3 uint8 BGR (OpenCV layout)."""
        if snapshot and self._snap is None:
            r = self.cfg["render"]
            self._snap = mujoco.Renderer(self.model, r["snap_height"], r["snap_width"])
        r = self.cfg["render"]
        rend = self._snap if snapshot else self.renderer
        rend.update_scene(self.data, camera=camera, scene_option=self.opt)
        effects = snapshot or r["gate_effects"]
        flags = rend.scene.flags
        flags[mujoco.mjtRndFlag.mjRND_SHADOW] = int(effects and r["shadows"])
        flags[mujoco.mjtRndFlag.mjRND_REFLECTION] = int(effects and r["reflection"])
        return np.ascontiguousarray(rend.render()[:, :, ::-1])
