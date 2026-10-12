"""Supervisor driving real child processes (crash, hang, then success)."""

import json
import subprocess
import sys
from pathlib import Path

from src.watchdog.supervisor import Supervisor
from tests.test_supervisor import CFG

FIXTURE = Path(__file__).parent / "fixtures" / "child.py"


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
