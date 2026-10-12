import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fault_window_for_spike():
    chaos = load("chaos")
    from src.core.defaults import DEFAULTS
    onset, end = chaos.fault_window("thermal_spike", DEFAULTS["policy"])
    assert 30 <= onset <= 32 and 35 <= end <= 37


def test_chaos_spike_recovers():
    chaos = load("chaos")
    r = chaos.run_scenario("thermal_spike", 50.0)
    assert r["deepest_rung"] == 3 and r["recover_s"] is not None


def test_line_limit_checker(tmp_path):
    chk = load("check_line_limit")
    (tmp_path / "ok.py").write_text("x = 1\n" * 5)
    (tmp_path / "big.py").write_text("x = 1\n" * 200)
    assert [p.name for p, _ in chk.offenders(tmp_path)] == ["big.py"]
