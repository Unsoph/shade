"""SQLite decision log: persistence, ordering, JSON round-trip."""

import threading

from src.core.decision.engine import DecisionEngine
from src.core.decision.log import DecisionLog
from tests.helpers import policy, run_trace


def test_records_decision_with_reasons():
    log = DecisionLog()
    eng = DecisionEngine(policy(), n_rungs=4)
    for d in run_trace(eng, [82]):
        if d.changed:
            log.record_decision(d)
    row = log.recent()[0]
    assert row["kind"] == "decision" and row["action"] == "degrade"
    assert (row["from_rung"], row["to_rung"]) == (0, 3)
    assert row["to_state"] == "CRITICAL"
    assert "critical" in row["reasons"][0]
    assert row["detail"]["temp"] == 82


def test_events_newest_first_and_filter():
    log = DecisionLog()
    log.record_event("swap_done", {"stall_ms": 0.4}, ts=1.0)
    log.record_event("camera_reconnect", {"attempt": 1}, ts=2.0)
    assert [r["kind"] for r in log.recent()] == ["camera_reconnect", "swap_done"]
    only = log.recent(kind="swap_done")
    assert len(only) == 1 and only[0]["detail"]["stall_ms"] == 0.4
    assert log.count() == 2 and log.count("swap_done") == 1


def test_file_backed_log_persists(tmp_path):
    path = tmp_path / "sub" / "shade.db"
    log = DecisionLog(path)
    log.record_event("x", {"a": 1})
    log.close()
    assert DecisionLog(path).count() == 1


def test_concurrent_writers():
    log = DecisionLog()

    def work():
        for _ in range(50):
            log.record_event("tick")

    threads = [threading.Thread(target=work) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert log.count("tick") == 200
