"""Supervisor: keep the engine process alive and recover it safely.

Detects exits (crash, OOM kill) and hangs (heartbeat stops), restarts with
exponential backoff, and starts crashed engines on the emergency rung so a
fault that caused the crash is not immediately re-triggered. The engine
then climbs back up through the normal thermal-gated upgrade path.

All time, process and notification functions are injectable for tests.
"""

import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable

from src.watchdog.heartbeat import read_heartbeat
from src.watchdog.sd_notify import notify

logger = logging.getLogger(__name__)
EMERGENCY_RUNG = -1  # last rung of the ladder


@dataclass(frozen=True)
class ChildExit:
    reason: str            # "exited" | "hang"
    returncode: int | None
    runtime_s: float


class Supervisor:
    def __init__(self, build_cmd: Callable[[int | str], list[str]], cfg: dict,
                 initial_rung: Callable[[], int | str],
                 on_event: Callable[[str, dict], None] = lambda k, d: None,
                 clock=time.time, sleep=time.sleep, spawn=subprocess.Popen,
                 sd_notify=notify, wait: Callable[[float], bool] | None = None):
        self._build, self._cfg = build_cmd, cfg
        self._initial_rung = initial_rung
        self._event, self._clock, self._sleep = on_event, clock, sleep
        self._spawn, self._notify = spawn, sd_notify
        self._stop = threading.Event()
        # interruptible backoff wait; True means stop was requested
        self._wait = wait or self._stop.wait

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> int:
        """Supervise until clean exit (0), stop request, or give-up (1)."""
        cfg = self._cfg
        backoff, failures, rung = cfg["backoff_initial_s"], 0, self._initial_rung()
        self._notify("READY=1")
        while not self._stop.is_set():
            proc = self._spawn(self._build(rung))
            self._event("child_started", {"pid": proc.pid, "rung": str(rung)})
            result = self._watch(proc)
            if self._stop.is_set():
                return 0
            if result.reason == "exited" and result.returncode == 0:
                logger.info("Engine exited cleanly.")
                return 0
            if result.runtime_s >= cfg["stable_after_s"]:
                failures, backoff = 0, cfg["backoff_initial_s"]
            failures += 1
            self._event("child_restart", {
                "reason": result.reason, "returncode": result.returncode,
                "runtime_s": round(result.runtime_s, 1), "attempt": failures,
                "backoff_s": backoff})
            logger.error("Engine %s (rc=%s) after %.0fs; restart %d/%d in %.1fs",
                         result.reason, result.returncode, result.runtime_s,
                         failures, cfg["max_restarts"], backoff)
            if failures > cfg["max_restarts"]:
                self._event("supervisor_gave_up", {"failures": failures})
                logger.error("Giving up after %d consecutive failures.", failures)
                return 1
            if self._wait(backoff):
                return 0
            backoff = min(backoff * cfg["backoff_factor"], cfg["backoff_max_s"])
            rung = EMERGENCY_RUNG
        return 0

    def _watch(self, proc) -> ChildExit:
        cfg, started = self._cfg, self._clock()
        while not self._stop.is_set():
            code = proc.poll()
            now = self._clock()
            if code is not None:
                return ChildExit("exited", code, now - started)
            beat = read_heartbeat(cfg["heartbeat_path"])
            fresh = beat and beat.get("pid") == proc.pid and beat["ts"] >= started
            limit = cfg["hang_timeout_s"] if fresh else cfg["startup_grace_s"]
            idle = now - (beat["ts"] if fresh else started)
            if idle > limit:
                self._terminate(proc)
                return ChildExit("hang", proc.poll(), now - started)
            if fresh:
                self._notify("WATCHDOG=1")
            self._sleep(cfg["poll_s"])
        self._terminate(proc)
        return ChildExit("exited", proc.poll(), self._clock() - started)

    def _terminate(self, proc) -> None:
        if proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=self._cfg["kill_timeout_s"])
        except subprocess.TimeoutExpired:
            logger.warning("Child ignored SIGTERM; killing.")
            proc.kill()
            proc.wait()
