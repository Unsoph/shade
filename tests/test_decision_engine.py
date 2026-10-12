"""Decision engine behaviour on scripted traces."""

from src.core.decision.engine import DecisionEngine
from src.core.decision.states import State
from tests.helpers import policy, run_trace, snap

N = 4  # rungs 0..3


def engine(**over):
    return DecisionEngine(policy(**over), n_rungs=N)


def test_cool_trace_stays_nominal():
    eng = engine()
    out = run_trace(eng, [50] * 60)
    assert all(d.rung == 0 and d.state == State.NOMINAL for d in out)


def test_degrade_needs_confirm_samples():
    eng = engine()
    out = run_trace(eng, [72, 72, 72, 72])
    assert [d.rung for d in out] == [0, 0, 1, 1]
    assert out[2].action == "degrade" and out[2].state == State.DEGRADED
    assert "warm" in out[2].reasons[0]


def test_single_spike_is_ignored():
    eng = engine()
    out = run_trace(eng, [50, 72, 50, 50, 72, 50, 50, 50])
    assert all(d.rung == 0 for d in out)


def test_critical_bypasses_confirm_and_dwell():
    eng = engine()
    out = run_trace(eng, [50, 82])
    assert out[1].rung == 3 and out[1].action == "degrade"
    assert out[1].state == State.CRITICAL


def test_no_upgrade_inside_hysteresis_band():
    eng = engine()
    run_trace(eng, [82])  # -> rung 3
    out = run_trace(eng, [70] * 120, start=1)  # between gate and degrade
    assert out[-1].rung == 3


def test_upgrade_is_one_step_with_hold_per_step():
    eng = engine()
    run_trace(eng, [82])
    out = run_trace(eng, [55] * 100, start=1)
    rungs = [d.rung for d in out]
    ups = [i for i in range(1, len(rungs)) if rungs[i] < rungs[i - 1]]
    assert len(ups) >= 2
    assert all(rungs[i] - rungs[i - 1] == -1 for i in ups)
    assert ups[1] - ups[0] >= 30  # recover_hold_s between steps
    assert any(d.state == State.RECOVERING for d in out)


def test_oscillation_does_not_flap():
    eng = engine()
    temps = [66, 76] * 60
    out = run_trace(eng, temps)
    changes = sum(1 for d in out if d.changed)
    assert changes <= 3


def test_undervoltage_is_power_warning_and_degrades():
    eng = engine()
    out = run_trace(eng, [50] * 5, throttle="Undervoltage")
    assert out[-1].state == State.POWER_WARNING
    assert out[-1].rung == 2
    assert any("power" in r for r in out[-1].reasons)


def test_swap_pressure_is_os_contention():
    eng = engine()
    out = run_trace(eng, [50] * 5, swap=40.0)
    assert out[-1].state == State.OS_CONTENTION and out[-1].rung == 2


def test_rising_temperature_raises_pressure_level():
    steady = engine()
    flat = run_trace(steady, [71] * 12)
    rising = engine()
    # 62 -> 71 at 0.9C/s: slope >= 0.5 while warm adds one pressure level
    ramp = run_trace(rising, [62 + 0.9 * i for i in range(11)])
    assert max(d.signals["level"] for d in flat) == 1
    assert ramp[-1].signals["level"] == 2
    assert any("rising" in r for r in ramp[-1].reasons)


def test_unavailable_rung_is_skipped():
    eng = engine()
    eng.mark_unavailable(1)
    out = run_trace(eng, [72] * 5)
    assert out[-1].rung == 2


def test_input_fault_sets_fault_state_without_degrading():
    eng = engine()
    out = run_trace(eng, [50] * 5, fault="frozen")
    assert out[-1].state == State.FAULT and out[-1].rung == 0
    assert "input fault: frozen" in out[-1].reasons


def test_fps_signal_when_enabled():
    eng = engine(min_fps=8.0, fps_grace_s=0.0)
    out = run_trace(eng, [50] * 5, fps=3.0)
    assert out[-1].rung == 1 and "fps" in out[-1].reasons[0]


def test_force_rung_resyncs_after_failed_swap():
    eng = engine()
    run_trace(eng, [72] * 4)
    eng.force_rung(0, now=10.0)
    assert eng.rung == 0


def test_label_churn_is_not_notable():
    eng = engine()
    run_trace(eng, [82])  # -> rung 3
    out = run_trace(eng, [64, 65.4] * 20, start=1)
    assert not any(d.notable for d in out)
