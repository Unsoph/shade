"""Supervised launch: run the engine as a child under the Supervisor."""

import logging
import signal
import sys
from pathlib import Path

from src.core.config import PROJECT_ROOT, resolve_path
from src.core.decision.log import DecisionLog
from src.watchdog.state_store import StateStore
from src.watchdog.supervisor import Supervisor

logger = logging.getLogger(__name__)
VALUE_FLAGS = {"--start-rung", "--heartbeat"}
BOOL_FLAGS = {"--supervised"}


def strip_args(argv: list[str]) -> list[str]:
    """Remove the flags the supervisor sets itself, with their values."""
    out, skip = [], False
    for tok in argv:
        if skip:
            skip = False
        elif tok in VALUE_FLAGS:
            skip = True
        elif tok.split("=")[0] in VALUE_FLAGS | BOOL_FLAGS:
            continue
        else:
            out.append(tok)
    return out


def supervise(config: dict, argv: list[str]) -> int:
    """Run `run.py` under a supervisor until it exits cleanly."""
    wd = config["watchdog"]
    wd = {**wd, "heartbeat_path": str(resolve_path(wd["heartbeat_path"]))}
    base = strip_args(argv)
    log = DecisionLog(resolve_path(config["policy"]["db_path"]))

    def build_cmd(rung):
        return [sys.executable, str(Path(PROJECT_ROOT) / "run.py"), *base,
                "--heartbeat", wd["heartbeat_path"], "--start-rung", str(rung)]

    def initial_rung():
        saved = StateStore(resolve_path(wd["state_path"])).load(wd["lkg_max_age_s"])
        if saved:
            logger.info("Resuming on last known-good rung '%s'.", saved["rung"])
            return saved["rung"]
        return 0

    sup = Supervisor(build_cmd, wd, initial_rung, on_event=log.record_event)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: sup.stop())
    try:
        return sup.run()
    finally:
        log.close()
