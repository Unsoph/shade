"""Warehouse workers in hi-vis vests that walk the aisles (MuJoCo mocap).

Each worker is five kinematic mocap bodies (torso with head and helmet, two
legs, two arms) with collisions off. Workers walk between aisle nodes that
have a clear straight path, at a random pace, sometimes stop for a few
seconds, and swing their limbs in step with the distance walked. Every
choice comes from the seeded RNG.
"""

import math

from src.sim.amr.mjcf_props import f

VESTS = ["0.95 0.85 0.05 1", "1 0.45 0.05 1"]
TROUSERS = ["0.12 0.14 0.22 1", "0.25 0.25 0.25 1", "0.2 0.17 0.12 1"]
SKIN = ["0.87 0.7 0.58 1", "0.6 0.42 0.3 1", "0.42 0.28 0.2 1"]
HELMETS = ["0.97 0.97 0.97 1", "0.95 0.8 0.05 1"]
TORSO_Z, STRIDE_M = 1.16, 1.4
LIMBS = {"leg_l": (0, 0.1, -0.3), "leg_r": (0, -0.1, -0.3),
         "arm_l": (0, 0.24, 0.26), "arm_r": (0, -0.24, 0.26)}
NOCOL = 'contype="0" conaffinity="0"'


def quat_zy(yaw: float, pitch: float = 0.0):
    """Quaternion (w, x, y, z) for yaw about z after pitch about y."""
    cz, sz, cy, sy = math.cos(yaw / 2), math.sin(yaw / 2), math.cos(pitch / 2), math.sin(pitch / 2)
    return (cz * cy, -sz * sy, cz * sy, sz * cy)


def worker_xml(i: int, rng) -> str:
    pick = lambda opts: opts[int(rng.integers(len(opts)))]  # noqa: E731
    trousers, skin = pick(TROUSERS), pick(SKIN)
    out = [f'<body name="w{i}_torso" mocap="true" pos="0 0 -5">'
           f'<geom type="box" size="0.12 0.19 0.3" rgba="{pick(VESTS)}" {NOCOL}/>'
           f'<geom type="box" size="0.125 0.195 0.025" pos="0 0 -0.1" rgba="0.85 0.85 0.85 1" {NOCOL}/>'
           f'<geom type="sphere" size="0.11" pos="0 0 0.43" rgba="{skin}" {NOCOL}/>'
           f'<geom type="cylinder" size="0.125 0.045" pos="0 0 0.55" rgba="{pick(HELMETS)}" {NOCOL}/>'
           '</body>']
    for name in LIMBS:
        leg = name.startswith("leg")
        half, colour = (0.42, trousers) if leg else (0.29, skin)
        w = 0.07 if leg else 0.045
        out.append(f'<body name="w{i}_{name}" mocap="true" pos="0 0 -5">'
                   f'<geom type="box" size="{f(w, w, half)}" pos="0 0 {-half:.3g}" '
                   f'rgba="{colour}" {NOCOL}/></body>')
    return "".join(out)


def clear(a, b, rects, step=0.2) -> bool:
    n = max(1, int(math.dist(a, b) / step))
    for k in range(n + 1):
        x, y = a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n
        if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rects):
            return False
    return True


def aisle_graph(cfg: dict, rects):
    nodes = [(x, y) for x in cfg["grid_x"] for y in cfg["grid_y"]
             if clear((x, y), (x, y), rects)]
    links = [[j for j, b in enumerate(nodes) if j != i and (a[0] == b[0] or a[1] == b[1])
              and clear(a, b, rects)] for i, a in enumerate(nodes)]
    return nodes, links


class Worker:
    def __init__(self, i, rng, nodes, links, cfg):
        self.i, self.rng, self.nodes, self.links = i, rng, nodes, links
        self.node = int(rng.integers(len(nodes)))
        self.x, self.y = nodes[self.node]
        sp = rng.normal(cfg["speed_mean"], cfg["speed_sd"])
        self.speed = float(min(max(sp, 0.6), 1.8))
        self.pause_p, self.pause_s = cfg["pause_prob"], cfg["pause_s"]
        self.yaw, self.walked, self.wait = float(rng.uniform(-math.pi, math.pi)), 0.0, 0.0
        self._next()

    def _next(self) -> None:
        options = self.links[self.node] or [self.node]
        self.node = options[int(self.rng.integers(len(options)))]
        if self.rng.random() < self.pause_p:
            self.wait = float(self.rng.uniform(*self.pause_s))

    def step(self, dt: float) -> float:
        """Advance dt seconds; returns the limb swing angle (rad)."""
        if self.wait > 0:
            self.wait -= dt
            return 0.0
        tx, ty = self.nodes[self.node]
        dist = math.hypot(tx - self.x, ty - self.y)
        move = min(self.speed * dt, dist)
        if dist > 1e-6:
            self.yaw = math.atan2(ty - self.y, tx - self.x)
            self.x += move * (tx - self.x) / dist
            self.y += move * (ty - self.y) / dist
        self.walked += move
        if dist - move < 0.05:
            self._next()
        return 0.45 * math.sin(2 * math.pi * self.walked / STRIDE_M)

    def poses(self, swing: float):
        """(body suffix, position, quaternion) for each mocap body."""
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        torso = (self.x, self.y, TORSO_Z)
        out = [("torso", torso, quat_zy(self.yaw))]
        for name, (dx, dy, dz) in LIMBS.items():
            sign = 1 if name.endswith("_l") else -1
            angle = sign * swing * (1.0 if name.startswith("leg") else -0.8)
            pos = (torso[0] + c * dx - s * dy, torso[1] + s * dx + c * dy, torso[2] + dz)
            out.append((name, pos, quat_zy(self.yaw, angle)))
        return out
