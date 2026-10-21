import random

from src.core.decision.advisor import ThermalAdvisor
from src.core.decision.thermal_model import ThermalModel
from src.core.defaults import DEFAULTS
from src.sim.plant import PlantConfig, ThermalPlant


def drive(model, plant, utils, seconds=1800, seed=0):
    """Run the plant under a repeating utilisation schedule."""
    rng = random.Random(seed)
    temp, t = plant.temp, 0
    for i in range(seconds):
        util = utils[(i // 120) % len(utils)]
        temp, _ = plant.step(util, 1.0, t)
        t += 1
        model.observe(t, temp, util)
    return rng


def test_model_recovers_true_steady_state_with_excitation():
    plant = ThermalPlant(PlantConfig(ambient_c=35, tau_s=80, k_c=50, noise_c=0.2), 1)
    model = ThermalModel({"tau_s": 200, "ambient_c": 20, "k_c": 90})  # wrong prior
    drive(model, plant, [0.9, 0.2, 0.6, 0.3], seconds=3000)
    for u in (0.2, 0.5, 0.9):
        assert abs(model.steady_state(u) - (35 + 50 * u)) < 3.0
    assert 50 < model.tau_s < 130


def test_uncertainty_shrinks_with_data():
    plant = ThermalPlant(PlantConfig(noise_c=0.2), 2)
    model = ThermalModel()
    before = model.steady_state(0.8, z=1) - model.steady_state(0.8)
    drive(model, plant, [0.9, 0.2], seconds=2400)
    after = model.steady_state(0.8, z=1) - model.steady_state(0.8)
    assert after < before


def test_throttled_samples_are_excluded():
    model = ThermalModel()
    model.observe(0, 50, 0.5)
    model.observe(10, 52, 0.5, valid=False)  # window restarts, no update
    assert model.n_updates == 0


def test_advisor_prefers_best_sustainable_rung():
    cfg = {**DEFAULTS["policy"]["forecast"], "min_updates": 0, "z": 0.0}
    adv = ThermalAdvisor([1.0, 0.5, 0.25, 0.1], cfg)
    plant = ThermalPlant(PlantConfig(ambient_c=30, k_c=60, noise_c=0.1), 3)
    temp, t = plant.temp, 0
    utils = [0.95, 0.5, 0.25, 0.1]
    for i in range(2400):
        rung = (i // 150) % 4  # cycle through rungs so each is measured
        temp, _ = plant.step(utils[rung], 1.0, t)
        t += 1
        adv.observe(t, temp, rung, utils[rung], False)
    # steady states: 87, 60, 45, 36 C -> first rung <= 68 C (long horizon) is 1
    assert adv.floor(temp, 4) == 1


def test_floor_is_zero_until_ready():
    adv = ThermalAdvisor([1, 0.5], DEFAULTS["policy"]["forecast"])
    assert adv.floor(90.0, 2) == 0
