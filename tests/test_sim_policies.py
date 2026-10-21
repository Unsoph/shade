import logging

from src.sim.loop import simulate
from src.sim.plant import PlantConfig, ThermalPlant
from src.sim.policies import Shade, Static, Thermostat
from src.sim.profile import ASSUMED

REL = [p.util for p in ASSUMED]


def test_plant_heats_cools_and_throttles():
    plant = ThermalPlant(PlantConfig(ambient_c=35, noise_c=0), 0)
    ever = False
    for t in range(1500):
        plant.step(1.0, 1.0, t)
        ever = ever or plant.throttled
    assert ever and plant.temp > 70  # duty-cycles around the firmware limit
    for t in range(1500, 3000):
        plant.step(0.0, 1.0, t)
    assert not plant.throttled and plant.temp < 40


def test_policy_ordering_in_hot_room():
    logging.disable(logging.CRITICAL)
    cfg = PlantConfig(ambient_c=35)
    hot = simulate(Static(0), cfg, ASSUMED, 1800, seed=1)
    safe = simulate(Static(3), cfg, ASSUMED, 1800, seed=1)
    shade = simulate(Shade("s", 4, REL), cfg, ASSUMED, 1800, seed=1)
    assert hot.throttled_pct > 10 and safe.throttled_pct == 0
    assert shade.throttled_pct == 0
    assert safe.utility < shade.utility


def test_thermostat_flaps_more_than_shade():
    logging.disable(logging.CRITICAL)
    cfg = PlantConfig(ambient_c=25)
    th = simulate(Thermostat(4), cfg, ASSUMED, 3600, seed=2)
    sh = simulate(Shade("s", 4, REL), cfg, ASSUMED, 3600, seed=2)
    assert th.switches_per_h >= sh.switches_per_h
