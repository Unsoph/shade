"""Watchdog: heartbeat and last-known-good store."""

import json

from src.core.decision.states import Decision, State
from src.watchdog.heartbeat import Heartbeat, read_heartbeat
from tests.helpers import Clock
from src.watchdog.state_store import KnownGoodRecorder, StateStore



# -- heartbeat -----------------------------------------------------------
def test_heartbeat_is_rate_limited_and_atomic(tmp_path):
    clk = Clock()
    hb = Heartbeat(tmp_path / "sub" / "hb.json", interval_s=1.0, clock=clk)
    hb.beat(1)
    clk.t += 0.2
    hb.beat(2)  # skipped: too soon
    assert read_heartbeat(tmp_path / "sub" / "hb.json")["frames"] == 1
    clk.t += 1.0
    hb.beat(3, idle=True)
    beat = read_heartbeat(tmp_path / "sub" / "hb.json")
    assert beat["frames"] == 3 and beat["idle"] is True
    assert not list((tmp_path / "sub").glob("*.tmp"))


def test_read_heartbeat_handles_missing_and_corrupt(tmp_path):
    assert read_heartbeat(tmp_path / "none.json") is None
    (tmp_path / "bad.json").write_text("{not json")
    assert read_heartbeat(tmp_path / "bad.json") is None


# -- last known good -----------------------------------------------------
def test_state_store_freshness(tmp_path):
    store = StateStore(tmp_path / "lkg.json")
    assert store.load(600) is None
    store.save("small-320", 2, ts=1000.0)
    assert store.load(600, now=1500.0)["rung"] == "small-320"
    assert store.load(600, now=2000.0) is None  # too old


def _decision(rung, state=State.DEGRADED):
    return Decision(0, state, rung, rung, state, "hold")


def test_recorder_saves_only_after_stable_period(tmp_path):
    clk, store = Clock(), StateStore(tmp_path / "lkg.json")
    rec = KnownGoodRecorder(store, ["a", "b", "c"], 60.0, clock=clk)
    rec(_decision(1))
    clk.t += 30
    rec(_decision(1))
    assert store.load(1e9, now=clk.t) is None
    clk.t += 40
    rec(_decision(1))
    assert store.load(1e9, now=clk.t)["rung"] == "b"


def test_recorder_ignores_critical_periods(tmp_path):
    clk, store = Clock(), StateStore(tmp_path / "lkg.json")
    rec = KnownGoodRecorder(store, ["a", "b"], 60.0, clock=clk)
    for _ in range(10):
        clk.t += 30
        rec(_decision(1, State.CRITICAL))
    assert store.load(1e9, now=clk.t) is None
