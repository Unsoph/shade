"""Watchdog: heartbeat, last-known-good store, and the supervisor."""

import json
import subprocess
import sys
from pathlib import Path

from src.core.decision.states import Decision, State
from src.watchdog.heartbeat import Heartbeat, read_heartbeat
from src.watchdog.launcher import strip_args
from src.watchdog.state_store import KnownGoodRecorder, StateStore
from src.watchdog.supervisor import Supervisor

FIXTURE = Path(__file__).parent / "fixtures" / "child.py"


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def sleep(self, dt):
        self.t += dt

    def wait(self, dt):
        self.t += dt
        return False


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


# -- supervisor (fake processes, fake clock) -----------------------------
class FakeProc:
    _pid = 100

    def __init__(self, clk, exit_after=None, rc=0):
        FakeProc._pid += 1
        self.pid, self._clk, self._rc = FakeProc._pid, clk, rc
        self._at = None if exit_after is None else clk() + exit_after
        self.terminated = False

    def poll(self):
        if self.terminated:
            return -15
        return self._rc if self._at is not None and self._clk() >= self._at \
            else None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True

    def wait(self, timeout=None):
        return self.poll()


CFG = {
    "heartbeat_path": "", "hang_timeout_s": 5.0, "startup_grace_s": 10.0,
    "poll_s": 1.0, "backoff_initial_s": 2.0, "backoff_factor": 2.0,
    "backoff_max_s": 10.0, "stable_after_s": 100.0, "max_restarts": 3,
    "kill_timeout_s": 1.0,
}


def make_sup(tmp_path, procs, clk, **over):
    cfg = {**CFG, "heartbeat_path": str(tmp_path / "hb.json"), **over}
    cmds, events, notes = [], [], []
    it = iter(procs)

    def spawn(cmd):
        cmds.append(cmd)
        return next(it)

    sup = Supervisor(lambda rung: ["engine", str(rung)], cfg, lambda: 0,
                     on_event=lambda k, d: events.append((k, d)),
                     clock=clk, sleep=clk.sleep, spawn=spawn,
                     sd_notify=notes.append, wait=clk.wait)
    return sup, cmds, events, notes


def test_clean_exit_is_not_restarted(tmp_path):
    clk = Clock()
    sup, cmds, events, notes = make_sup(tmp_path, [FakeProc(clk, 3, 0)], clk)
    assert sup.run() == 0 and len(cmds) == 1
    assert notes[0] == "READY=1"


def test_crash_restarts_on_emergency_rung_with_backoff(tmp_path):
    clk = Clock()
    procs = [FakeProc(clk, 3, 1), FakeProc(clk, 3, 1), FakeProc(clk, 3, 0)]
    sup, cmds, events, _ = make_sup(tmp_path, procs, clk)
    assert sup.run() == 0
    assert [c[1] for c in cmds] == ["0", "-1", "-1"]
    backoffs = [d["backoff_s"] for k, d in events if k == "child_restart"]
    assert backoffs == [2.0, 4.0]


def test_gives_up_after_max_restarts(tmp_path):
    clk = Clock()
    procs = [FakeProc(clk, 2, 1) for _ in range(6)]
    sup, cmds, events, _ = make_sup(tmp_path, procs, clk, max_restarts=2)
    assert sup.run() == 1 and len(cmds) == 3
    assert events[-1][0] == "supervisor_gave_up"


def test_stable_run_resets_backoff(tmp_path):
    clk = Clock()
    procs = [FakeProc(clk, 3, 1), FakeProc(clk, 150, 1), FakeProc(clk, 3, 0)]
    sup, _, events, _ = make_sup(tmp_path, procs, clk,
                                 hang_timeout_s=1000, startup_grace_s=1000)
    sup.run()
    backoffs = [d["backoff_s"] for k, d in events if k == "child_restart"]
    assert backoffs == [2.0, 2.0]  # second failure followed a stable run


def test_hang_is_detected_and_killed(tmp_path):
    clk = Clock()
    hung = FakeProc(clk, None)  # never exits, never beats
    sup, _, events, _ = make_sup(tmp_path, [hung, FakeProc(clk, 2, 0)], clk)
    assert sup.run() == 0
    assert hung.terminated
    restart = next(d for k, d in events if k == "child_restart")
    assert restart["reason"] == "hang"


def test_fresh_heartbeat_prevents_hang_and_pings_systemd(tmp_path):
    clk = Clock()
    proc = FakeProc(clk, 30, 0)
    sup, _, events, notes = make_sup(tmp_path, [proc], clk,
                                     startup_grace_s=2.0)
    hb = Heartbeat(tmp_path / "hb.json", interval_s=0, clock=clk)
    orig_sleep = clk.sleep

    def beating_sleep(dt):
        hb_pid_patch(proc.pid)
        orig_sleep(dt)

    def hb_pid_patch(pid):
        (tmp_path / "hb.json").write_text(
            json.dumps({"pid": pid, "ts": clk.t, "frames": 1}))

    sup._sleep = beating_sleep
    assert sup.run() == 0 and not proc.terminated
    assert "WATCHDOG=1" in notes and not events[1:]


def test_stop_request_ends_supervision(tmp_path):
    clk = Clock()
    proc = FakeProc(clk, None)
    sup, _, _, _ = make_sup(tmp_path, [proc], clk, startup_grace_s=1e9,
                            hang_timeout_s=1e9)
    sup._sleep = lambda dt: sup.stop()
    assert sup.run() == 0 and proc.terminated


def test_strip_args_removes_supervisor_flags():
    argv = ["--supervised", "--fake", "--start-rung", "2",
            "--heartbeat=x", "--source", "0"]
    assert strip_args(argv) == ["--fake", "--source", "0"]


# -- supervisor with real subprocesses -----------------------------------
def test_real_processes_crash_hang_then_succeed(tmp_path):
    state = tmp_path / "state"
    cfg = {**CFG, "heartbeat_path": str(tmp_path / "hb.json"),
           "poll_s": 0.05, "hang_timeout_s": 0.6, "startup_grace_s": 3.0,
           "backoff_initial_s": 0.05, "backoff_max_s": 0.1,
           "kill_timeout_s": 2.0, "max_restarts": 5}
    env = {"SHADE_TEST_STATE": str(state), "PATH": "/usr/bin:/bin"}

    def build(rung):
        return [sys.executable, str(FIXTURE), "--heartbeat",
                cfg["heartbeat_path"], "--start-rung", str(rung)]

    events = []
    sup = Supervisor(build, cfg, lambda: 0,
                     on_event=lambda k, d: events.append((k, d)),
                     spawn=lambda cmd: subprocess.Popen(cmd, env=env),
                     sd_notify=lambda m: False)
    assert sup.run() == 0
    reasons = [d["reason"] for k, d in events if k == "child_restart"]
    assert reasons == ["exited", "hang"]
    rungs = [json.loads(line)[-1] for line in
             Path(str(state) + ".argv").read_text().splitlines()]
    assert rungs == ["0", "-1", "-1"]
