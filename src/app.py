"""Application assembly: builds the runtime and runs the pipeline."""

import logging
import time
from dataclasses import dataclass, field

from src.core.config import resolve_path
from src.core.controller import Controller
from src.core.decision.engine import DecisionEngine
from src.core.decision.log import DecisionLog
from src.core.hardware.hw_factory import create_hw_monitor
from src.core.health_monitor import HealthMonitor
from src.core.input_health import InputHealth
from src.core.ladder import Rung, available_rungs, parse_ladder, resolve_rung
from src.core.model_manager import ModelManager
from src.core.simulation import FAKE_LADDER, scale_policy
from src.watchdog.heartbeat import Heartbeat
from src.watchdog.state_store import KnownGoodRecorder, StateStore

logger = logging.getLogger(__name__)


@dataclass
class Runtime:
    config: dict
    policy: dict  # effective policy (timers scaled for simulation speed)
    rungs: list[Rung]
    log: DecisionLog
    health: HealthMonitor
    manager: ModelManager
    controller: Controller
    input_health: InputHealth
    heartbeat: object | None = None
    closers: list = field(default_factory=list)  # callables run at shutdown

    def close(self) -> None:
        self.health.stop_polling()
        for fn in reversed(self.closers):
            try:
                fn()
            except Exception:  # noqa: BLE001 - shutdown must continue
                logger.exception("Shutdown hook failed.")
        self.manager.close()
        self.log.close()


def build_runtime(config: dict, start_rung: int | str = 0, fake: bool = False,
                  db_path: str | None = None,
                  heartbeat_path: str | None = None) -> Runtime:
    """Wire engine, manager, health monitor and log together.

    start_rung may be an index, a negative index (-1 = emergency rung) or a
    rung name. heartbeat_path enables the watchdog heartbeat.
    """
    if fake:
        config["ladder"] = FAKE_LADDER
    rungs = available_rungs(parse_ladder(config))
    if not rungs:
        raise RuntimeError(
            "No usable ladder rungs: no model files found. Put yolov8n.onnx in "
            "models/ (see README) or run with --fake.")
    start_rung = resolve_rung(start_rung, rungs)

    speed = config["simulation"]["speed"] \
        if config["device"]["hardware"] == "simulated" else 1.0
    policy = scale_policy(config["policy"], speed)
    log = DecisionLog(db_path or resolve_path(policy["db_path"]))
    health = HealthMonitor(create_hw_monitor(config))
    engine = DecisionEngine(policy, len(rungs), start_rung)
    manager = ModelManager(rungs, config)
    controller = Controller(engine, manager, health, log, rungs)
    manager.on_failure = controller.on_failure

    manager.load_initial(start_rung)
    rung = rungs[start_rung]
    backend = manager.backend
    health.set_model_info(rung.model.rsplit("/", 1)[-1], backend.backend_name,
                          start_rung, backend.vram_mb)
    health.set_control("NOMINAL", start_rung, rung.name)
    health.add_listener(controller.on_snapshot)
    logger.info("Ladder: %s | start rung %d '%s' | %s",
                [r.name for r in rungs], start_rung, rung.name,
                backend.backend_name)
    rt = Runtime(config, policy, rungs, log, health, manager, controller,
                 InputHealth(config["input"]))
    wd = config["watchdog"]
    if heartbeat_path:
        rt.heartbeat = Heartbeat(heartbeat_path, wd["heartbeat_interval_s"])
    if wd["state_path"]:
        controller.on_decision = KnownGoodRecorder(
            StateStore(resolve_path(wd["state_path"])),
            [r.name for r in rungs], wd["good_after_s"] / speed)
    obs = config["observability"]
    if obs["enabled"]:
        from src.observability.server import ObservabilityServer
        try:
            server = ObservabilityServer(health, log, obs["host"], obs["port"],
                                         obs["decisions_limit"]).start()
            rt.closers.append(server.stop)
        except OSError as exc:  # port busy: monitoring must not stop inference
            logger.warning("Observability disabled: %s", exc)
    return rt


def run(rt: Runtime, source, display: bool, max_frames: int,
        dashboard: bool = False, close: bool = True) -> int:
    """Run until the source ends, max_frames, or Ctrl+C. Returns frames.

    close=False leaves the log and models open so callers (tests, the
    chaos script) can inspect them; call rt.close() afterwards.
    """
    from src.video.pipeline import run_pipeline

    rt.health.start_polling(rt.policy["poll_interval_s"])
    if dashboard:
        from src.display.console_dashboard import start_dashboard_thread
        start_dashboard_thread(rt.health, refresh_rate=0.5)
    frames = 0
    try:
        frames = run_pipeline(rt, source, display, max_frames)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        time.sleep(0.05)
        if close:
            rt.close()
        else:
            rt.health.stop_polling()
        logger.info("Shutdown complete.")
    return frames
