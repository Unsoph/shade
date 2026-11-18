"""Assemble the MuJoCo warehouse scene (MJCF) from parameters and a seed.

Concrete floor with painted lanes, block walls and a roof, overhead lights
(one casting shadows), pallet racking full of cartons, pallet loads, a
packing table, pillars, cones, a parked forklift, walking workers and the
AMR itself. Returns the MJCF text and the worker objects that animate it.
"""

import math

from src.sim.amr import mjcf_props as mp
from src.sim.amr.mjcf_robot import robot_xml
from src.sim.amr.people import Worker, aisle_graph, worker_xml
from src.sim.amr.textures import write_textures

N_CARTON_TEX = 4


def _assets(tex: dict) -> str:
    cube = lambda n, path: f'<texture name="{n}" type="cube" file="{path}"/>'  # noqa: E731
    out = [f'<texture name="floor" type="2d" file="{tex["concrete"][0]}"/>',
           cube("wall_t", tex["wall"][0]), cube("conc_t", tex["concrete"][0]),
           cube("wood_t", tex["wood"][0]), cube("haz_t", tex["hazard"][0]),
           '<texture name="sky" type="skybox" builtin="gradient" rgb1="0.3 0.3 0.32" '
           'rgb2="0.12 0.12 0.13" width="64" height="64"/>',
           '<material name="floor" texture="floor" texrepeat="10 7" texuniform="true" reflectance="0.06"/>',
           '<material name="wall" texture="wall_t" texrepeat="4 1" texuniform="true"/>',
           '<material name="concrete_box" texture="conc_t"/>',
           '<material name="wood" texture="wood_t"/>', '<material name="hazard" texture="haz_t"/>',
           '<material name="upright" rgba="0.12 0.3 0.65 1" specular="0.3"/>',
           '<material name="beam" rgba="0.95 0.45 0.08 1" specular="0.3"/>',
           '<material name="deck" rgba="0.55 0.56 0.58 1"/>',
           '<material name="wrap" rgba="0.85 0.88 0.9 0.55" specular="0.6"/>',
           '<material name="lane" rgba="0.95 0.75 0.1 1"/>',
           '<material name="cone" rgba="0.98 0.42 0.08 1"/>',
           '<material name="forklift" rgba="0.95 0.75 0.1 1" specular="0.4"/>',
           '<material name="amr" rgba="0.95 0.55 0.1 1" specular="0.5"/>']
    for i, path in enumerate(tex["cardboard"]):
        out += [cube(f"card_t{i}", path), f'<material name="cardboard{i}" texture="card_t{i}"/>']
    ring = [f"{0.16 * math.cos(a):.3f} {0.16 * math.sin(a):.3f} 0"
            for a in (2 * math.pi * k / 16 for k in range(16))]
    out.append(f'<mesh name="cone" vertex="0 0 0.7 {" ".join(ring)}"/>')
    return "".join(out)


def _rects(w: dict, pad: float = 0.35):
    rects = []
    for cx, cy, length, depth, yaw in w["racks"]:
        a, b = (length, depth) if abs(math.sin(yaw)) < 0.5 else (depth, length)
        rects.append((cx - a / 2, cy - b / 2, cx + a / 2, cy + b / 2))
    rects += [(x - 0.65, y - 0.45, x + 0.65, y + 0.45) for x, y in w["pallets"]]
    rects += [(x - 0.3, y - 0.3, x + 0.3, y + 0.3) for x, y in w["pillars"]]
    fx, fy, _ = w["forklift"]
    rects += [(fx - 1.2, fy - 0.8, fx + 2.3, fy + 0.8), (w["table"][0] - 0.9, w["table"][1] - 0.5,
                                                         w["table"][0] + 0.9, w["table"][1] + 0.5)]
    return [(x0 - pad, y0 - pad, x1 + pad, y1 + pad) for x0, y0, x1, y1 in rects]


def build_scene(cfg: dict, rngs: dict, start_pose, tex_dir=None):
    w, hx, hy = cfg["world"], cfg["world"]["hall_m"][0] / 2, cfg["world"]["hall_m"][1] / 2
    wh, lay = w["wall_h_m"], rngs["layout"]
    tex = write_textures(lay, tex_dir, N_CARTON_TEX)
    body = [f'<geom type="plane" size="{mp.f(hx, hy, 0.1)}" material="floor"/>',
            mp.geom((0, 0, wh + 0.05), [2 * hx, 2 * hy, 0.1], 'rgba="0.25 0.25 0.27 1"')]
    for x, y, sx, sy in ((hx, 0, 0.2, 2 * hy), (-hx, 0, 0.2, 2 * hy),
                         (0, hy, 2 * hx, 0.2), (0, -hy, 2 * hx, 0.2)):
        body.append(mp.geom((x, y, wh / 2), [sx, sy, wh], 'material="wall"', extra=""))
    body.append('<light pos="2 -1 4.7" dir="-0.2 0.1 -1" directional="false" castshadow="true" '
                'cutoff="85" exponent="2" diffuse="0.55 0.55 0.52" specular="0.2 0.2 0.2"/>')
    for x, y in w["ceiling_lights"]:
        body.append(f'<light pos="{mp.f(x, y, 4.6)}" dir="0 0 -1" castshadow="false" '
                    'cutoff="70" diffuse="0.22 0.22 0.21" specular="0 0 0"/>')
    lx0, lx1 = w["lanes_x"]
    body += [mp.lane(lx0, y, lx1, y) for y in w["lanes_y"]]
    for cx, cy, length, depth, yaw in w["racks"]:
        body += mp.rack(lay, cx, cy, length, depth, yaw, N_CARTON_TEX)
    for x, y in w["pallets"]:
        body += mp.pallet_load(lay, x, y, N_CARTON_TEX)
    for x, y in w["pillars"]:
        body += mp.pillar(x, y, height=wh)
    for x, y in w["cones"]:
        body += mp.cone(x, y)
    body += mp.forklift(*w["forklift"]) + mp.table(*w["table"])
    rnd, prng = cfg["random"], rngs["people"]
    friction = 1.2 * (1 + rngs["robot"].uniform(-1, 1) * rnd["friction_jitter"])
    payload = float(rngs["robot"].uniform(*rnd["payload_kg"]))
    robot, act = robot_xml(cfg["robot"], cfg["camera"], *start_pose, friction, payload)
    nodes, links = aisle_graph(cfg["people"], _rects(w))
    workers = [Worker(i, prng, nodes, links, cfg["people"]) for i in range(cfg["people"]["count"])]
    body += [robot] + [worker_xml(i, prng) for i in range(len(workers))]
    r = cfg["render"]
    xml = (f'<mujoco model="shade_warehouse"><option timestep="{cfg["sim"]["timestep_s"]}" '
           'integrator="implicitfast"/>'
           f'<visual><global offwidth="{r["snap_width"]}" offheight="{r["snap_height"]}"/>'
           '<quality shadowsize="2048"/><map znear="0.005" zfar="80"/>'
           '<headlight ambient="0.32 0.32 0.32" diffuse="0.25 0.25 0.25" specular="0 0 0"/></visual>'
           f'<asset>{_assets(tex)}</asset><worldbody>{"".join(body)}</worldbody>'
           f'<actuator>{act}</actuator></mujoco>')
    return xml, workers, {"friction": friction, "payload_kg": payload}
