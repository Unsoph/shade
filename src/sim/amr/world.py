"""Warehouse world for the AMR twin: floor, walls, shelves and walkers.

Shelves and walls are static colliders. Walkers are visual-only cylinders
that pace between two points; they never collide with the robot but do
appear in its camera, so the scene keeps moving while the robot is parked.
"""

import math

import pybullet as p
import pybullet_data

SHELF_COLOURS = [(0.20, 0.45, 0.85, 1), (0.25, 0.65, 0.35, 1), (0.80, 0.25, 0.25, 1),
                 (0.55, 0.40, 0.75, 1), (0.85, 0.75, 0.20, 1)]
WALL_COLOUR = (0.75, 0.75, 0.72, 1)
WALKER_COLOUR = (0.15, 0.15, 0.55, 1)
WALL_H, WALL_T = 1.2, 0.1
WALKER_R, WALKER_H = 0.25, 1.7


def connect(gui: bool, physics_hz: int) -> int:
    cid = p.connect(p.GUI if gui else p.DIRECT)
    p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=cid)
    p.setGravity(0, 0, -9.81, physicsClientId=cid)
    p.setTimeStep(1.0 / physics_hz, physicsClientId=cid)
    return cid


def static_box(cid: int, x, y, sx, sy, sz, colour) -> int:
    half = [sx / 2, sy / 2, sz / 2]
    col = p.createCollisionShape(p.GEOM_BOX, halfExtents=half, physicsClientId=cid)
    vis = p.createVisualShape(p.GEOM_BOX, halfExtents=half, rgbaColor=colour,
                              physicsClientId=cid)
    return p.createMultiBody(0, col, vis, [x, y, sz / 2], physicsClientId=cid)


class Walker:
    def __init__(self, cid: int, spec: dict):
        self.cid = cid
        self.a, self.b = spec["a"], spec["b"]
        self.speed = spec["speed"]
        self.length = math.dist(self.a, self.b)
        vis = p.createVisualShape(p.GEOM_CYLINDER, radius=WALKER_R, length=WALKER_H,
                                  rgbaColor=WALKER_COLOUR, physicsClientId=cid)
        self.body = p.createMultiBody(0, -1, vis, [*self.a, WALKER_H / 2],
                                      physicsClientId=cid)

    def position(self, t: float) -> tuple[float, float]:
        if self.length == 0:
            return tuple(self.a)
        s = (t * self.speed) % (2 * self.length)
        f = (s if s <= self.length else 2 * self.length - s) / self.length
        return (self.a[0] + f * (self.b[0] - self.a[0]),
                self.a[1] + f * (self.b[1] - self.a[1]))

    def move(self, t: float) -> None:
        x, y = self.position(t)
        p.resetBasePositionAndOrientation(self.body, [x, y, WALKER_H / 2], [0, 0, 0, 1],
                                          physicsClientId=self.cid)


class World:
    def __init__(self, cid: int, cfg: dict):
        self.cid = cid
        p.loadURDF("plane.urdf", physicsClientId=cid)
        half = cfg["arena_m"] / 2
        for x, y, sx, sy in ((half, 0, WALL_T, 2 * half), (-half, 0, WALL_T, 2 * half),
                             (0, half, 2 * half, WALL_T), (0, -half, 2 * half, WALL_T)):
            static_box(cid, x, y, sx, sy, WALL_H, WALL_COLOUR)
        for i, (x, y, sx, sy, h) in enumerate(cfg["shelves"]):
            static_box(cid, x, y, sx, sy, h, SHELF_COLOURS[i % len(SHELF_COLOURS)])
        self.walkers = [Walker(cid, w) for w in cfg["walkers"]]

    def step(self, t: float) -> None:
        for w in self.walkers:
            w.move(t)
