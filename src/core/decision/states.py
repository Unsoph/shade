"""Decision engine vocabulary: states and the Decision record."""

from dataclasses import dataclass, field
from enum import Enum


SOFT_STATES = frozenset({"DEGRADED", "CRITICAL", "RECOVERING"})


class State(str, Enum):
    """Operating state. Standard states plus Pi-specific and input faults."""

    NOMINAL = "NOMINAL"
    ELEVATED = "ELEVATED"          # warm, still on the best rung
    DEGRADED = "DEGRADED"          # running a lighter rung
    CRITICAL = "CRITICAL"          # on the last-resort rung
    RECOVERING = "RECOVERING"      # calm; waiting out the upgrade hold
    POWER_WARNING = "POWER_WARNING"    # undervoltage: fix the supply
    OS_CONTENTION = "OS_CONTENTION"    # memory/swap pressure
    FAULT = "FAULT"                # input fault (frozen/dark camera)


@dataclass(frozen=True)
class Decision:
    """One evaluation result. `changed` means the rung should move."""

    timestamp: float
    state: State
    rung: int
    prev_rung: int
    prev_state: State
    action: str  # "hold" | "degrade" | "upgrade"
    reasons: tuple[str, ...] = ()
    signals: dict = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return self.rung != self.prev_rung

    @property
    def state_changed(self) -> bool:
        return self.state != self.prev_state

    @property
    def notable(self) -> bool:
        """Worth logging: a rung move, or a state change that is not just
        label churn between DEGRADED / CRITICAL / RECOVERING."""
        if self.changed:
            return True
        if not self.state_changed:
            return False
        return not (self.state.value in SOFT_STATES
                    and self.prev_state.value in SOFT_STATES)
