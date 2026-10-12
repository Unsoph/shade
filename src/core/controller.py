"""Controller: glues the decision engine to the model manager and the log.

Runs on the health poll thread (on_snapshot) and on the manager's preload
thread (on_failure); a lock keeps the engine single-threaded.
"""

import logging
import threading
import time

from src.core.decision.engine import DecisionEngine
from src.core.decision.log import DecisionLog
from src.core.decision.states import Decision
from src.core.health_monitor import HealthMonitor
from src.core.ladder import Rung
from src.core.model_manager import ModelManager
from src.core.snapshots import HealthSnapshot
from src.core.swap import SwapResult

logger = logging.getLogger(__name__)


class Controller:
    def __init__(self, engine: DecisionEngine, manager: ModelManager,
                 health: HealthMonitor, log: DecisionLog, rungs: list[Rung]):
        self.engine, self.manager = engine, manager
        self.health, self.log, self.rungs = health, log, rungs
        self.last_decision: Decision | None = None
        self.on_decision = None  # optional hook(Decision), e.g. known-good store
        self._lock = threading.Lock()

    def on_snapshot(self, snap: HealthSnapshot) -> Decision:
        """Evaluate one telemetry sample and act on the decision."""
        with self._lock:
            decision = self.engine.evaluate(snap, now=snap.timestamp)
        self.last_decision = decision
        if decision.notable:
            self.log.record_decision(decision)
            logger.info("%s %s rung %d->%d: %s", decision.action.upper(),
                        decision.state.value, decision.prev_rung, decision.rung,
                        "; ".join(decision.reasons))
        if decision.changed:
            self.manager.request(decision.rung)
        self.health.set_control(state=decision.state.value)
        if self.on_decision:
            self.on_decision(decision)
        return decision

    def on_swap(self, result: SwapResult, first_frame_ms: float) -> None:
        """Record a completed swap (called from the inference thread)."""
        self.health.set_control(rung=result.idx, rung_name=result.rung.name)
        self.health.set_runtime(swap_stall_ms=first_frame_ms)
        backend = self.manager.backend
        self.health.set_model_info(
            model_name=result.rung.model.rsplit("/", 1)[-1],
            backend=backend.backend_name, tier=result.idx,
            vram=backend.vram_mb)
        self.log.record_event("swap_done", {
            "rung": result.rung.name, "idx": result.idx,
            "swap_ms": round(result.swap_ms, 3),
            "first_frame_ms": round(first_frame_ms, 1),
            "load_s": round(result.load_s, 2), "light": result.light,
        })

    def on_failure(self, idx: int, reason: str) -> None:
        """A swap could not complete: stop targeting that rung."""
        with self._lock:
            self.engine.mark_unavailable(idx)
            self.engine.force_rung(self.manager.index, time.time())
        self.log.record_event("swap_failed", {
            "rung": self.rungs[idx].name, "idx": idx, "reason": reason})
