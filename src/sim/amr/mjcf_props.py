"""MJCF snippets for warehouse props: racks with cartons, pallets, cones,
pillars, floor markings, a packing table and a parked forklift.

Visual geoms are in group 0 with collisions off; anything the robot could
hit gets one invisible collision box in group 3 (hidden in renders).
"""

import math

VIS = 'contype="0" conaffinity="0"'
HIDDEN = 'group="3" rgba="0 0 0 0"'


def f(*v) -> str:
    return " ".join(f"{x:.4g}" for x in v)


def geom(pos, size, look, yaw=0.0, kind="box", extra=VIS) -> str:
    """look: 'material="x"' or 'rgba="r g b a"'. size = full extents for boxes."""
    half = [s / 2 for s in size] if kind == "box" else size
    return (f'<geom type="{kind}" pos="{f(*pos)}" size="{f(*half)}" '
            f'euler="0 0 {math.degrees(yaw):.4g}" {look} {extra}/>')


def solid(pos, size, yaw=0.0) -> str:
    return geom(pos, size, HIDDEN, yaw, extra="")


def local(cx, cy, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return lambda dx, dy, z: (cx + c * dx - s * dy, cy + s * dx + c * dy, z)


def cartons(rng, at, length, depth, z, fill, max_h, yaw, n_tex) -> list[str]:
    out, x = [], -length / 2 + 0.05
    while x < length / 2 - 0.3:
        w = rng.uniform(0.35, 0.8)
        if x + w > length / 2 - 0.05:
            break
        if rng.random() < fill:
            h = rng.uniform(0.25, max(max_h, 0.26))
            d = rng.uniform(0.5, 0.95) * depth
            tex = int(rng.integers(n_tex))
            out.append(geom(at(x + w / 2, rng.uniform(-0.05, 0.05), z + h / 2), [w, d, h],
                            f'material="cardboard{tex}"', yaw + rng.uniform(-0.06, 0.06)))
        x += w + rng.uniform(0.03, 0.15)
    return out


def rack(rng, cx, cy, length, depth, yaw, n_tex, height=3.2,
         levels=(0.15, 1.2, 2.25), fill=0.75) -> list[str]:
    at, out = local(cx, cy, yaw), []
    bays = max(1, round(length / 2.7))
    for i in range(bays + 1):
        for dy in (-depth / 2, depth / 2):
            out.append(geom(at(-length / 2 + i * length / bays, dy, height / 2),
                            [0.08, 0.08, height], 'material="upright"', yaw))
    for z in levels:
        for dy in (-depth / 2, depth / 2):
            out.append(geom(at(0, dy, z), [length, 0.06, 0.1], 'material="beam"', yaw))
        out.append(geom(at(0, 0, z + 0.03), [length, depth, 0.02], 'material="deck"', yaw))
        out += cartons(rng, at, length, depth, z + 0.04, fill,
                       0.9 if z < levels[-1] else 0.7, yaw, n_tex)
    out.append(solid(at(0, 0, height / 2), [length + 0.1, depth + 0.1, height], yaw))
    return out


def pallet_load(rng, x, y, n_tex, yaw=0.0) -> list[str]:
    at, out = local(x, y, yaw), []
    for dy in (-0.35, 0.0, 0.35):
        out.append(geom(at(0, dy, 0.05), [1.2, 0.1, 0.1], 'material="wood"', yaw))
    for dx in (-0.5, -0.25, 0.0, 0.25, 0.5):
        out.append(geom(at(dx, 0, 0.125), [0.12, 0.8, 0.025], 'material="wood"', yaw))
    z = 0.14
    for _ in range(int(rng.integers(1, 4))):
        h = rng.uniform(0.25, 0.45)
        out += cartons(rng, at, 1.2, 0.8, z, 0.9, h, yaw, n_tex)
        z += h
    if rng.random() < 0.4:
        out.append(geom(at(0, 0, 0.14 + (z - 0.14) / 2), [1.22, 0.82, z - 0.14],
                        'material="wrap"', yaw))
    out.append(solid(at(0, 0, z / 2), [1.25, 0.85, z], yaw))
    return out


def cone(x, y) -> list[str]:
    return [f'<geom type="mesh" mesh="cone" pos="{f(x, y, 0.03)}" material="cone" {VIS}/>',
            geom((x, y, 0.015), [0.36, 0.36, 0.03], 'material="cone"'),
            geom((x, y, 0.38), [0.085, 0.04], 'rgba="0.95 0.95 0.95 1"', kind="cylinder")]


def pillar(x, y, size=0.45, height=5.0) -> list[str]:
    return [geom((x, y, height / 2), [size, size, height], 'material="concrete_box"', extra=""),
            geom((x, y, 0.6), [size + 0.02, size + 0.02, 1.2], 'material="hazard"')]


def lane(x0, y0, x1, y1, width=0.1) -> str:
    return geom(((x0 + x1) / 2, (y0 + y1) / 2, 0.002), [math.hypot(x1 - x0, y1 - y0), width,
                0.004], 'material="lane"', math.atan2(y1 - y0, x1 - x0))


def table(x, y) -> list[str]:
    out = [geom((x, y, 0.88), [1.6, 0.8, 0.04], 'material="wood"')]
    for dx in (-0.72, 0.72):
        for dy in (-0.32, 0.32):
            out.append(geom((x + dx, y + dy, 0.43), [0.05, 0.05, 0.86], 'material="upright"'))
    return out + [solid((x, y, 0.45), [1.6, 0.8, 0.9])]


def forklift(x, y, yaw) -> list[str]:
    at, out = local(x, y, yaw), []
    parts = [((0, 0, 0.6), [1.8, 1.1, 0.9], 'material="forklift"'),
             ((-0.7, 0, 0.75), [0.5, 1.0, 0.6], 'rgba="0.2 0.2 0.2 1"'),
             ((-0.3, 0, 2.15), [1.0, 1.1, 0.06], 'rgba="0.08 0.08 0.08 1"')]
    for dy in (-0.5, 0.5):
        parts += [((-0.3, dy, 1.6), [0.06, 0.06, 1.1], 'rgba="0.08 0.08 0.08 1"'),
                  ((0.95, dy * 0.6, 1.3), [0.08, 0.1, 2.4], 'rgba="0.45 0.47 0.5 1"'),
                  ((1.6, dy * 0.6, 0.08), [1.2, 0.12, 0.05], 'rgba="0.45 0.47 0.5 1"')]
    out += [geom(at(*p), s, look, yaw) for p, s, look in parts]
    for dx in (-0.6, 0.6):
        for dy in (-0.55, 0.55):
            px, py, _ = at(dx, dy, 0)
            cy, sy, cx = math.cos(yaw / 2), math.sin(yaw / 2), math.cos(math.pi / 4)
            out.append(f'<geom type="cylinder" pos="{f(px, py, 0.25)}" size="0.25 0.1" '
                       f'quat="{f(cy * cx, cy * cx, sy * cx, sy * cx)}" '
                       f'rgba="0.08 0.08 0.08 1" {VIS}/>')
    return out + [solid(at(0.3, 0, 1.0), [2.6, 1.2, 2.0], yaw)]
