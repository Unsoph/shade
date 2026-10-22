import importlib.util
from pathlib import Path

from src.sim.plant import PlantConfig, ThermalPlant

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fit_recovers_known_plant():
    plant = ThermalPlant(PlantConfig(ambient_c=31, tau_s=70, k_c=55, noise_c=0.05), 4)
    rows, t = [], 0
    for i in range(3000):
        util = [0.9, 0.3, 0.6, 0.15][(i // 200) % 4]
        temp, _ = plant.step(util, 1.0, t)
        t += 1
        rows.append({"t_s": t, "temp_c": temp, "cpu_util": util, "throttled": 0})
    p = load("fit_plant").fit(rows)
    assert abs(p["tau_s"] - 70) < 15 and abs(p["k_c"] - 55) < 8
    assert abs(p["ambient_c"] - 31) < 4 and p["r2_rate"] > 0.5
