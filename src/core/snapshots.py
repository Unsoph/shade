"""Health snapshot — point-in-time system health, JSON-serializable."""

import time
from dataclasses import dataclass, field, asdict
import json


@dataclass(slots=True)
class HealthSnapshot:
    """Complete system health at a point in time.

    All fields have safe defaults so partial updates are fine.
    """

    # Timing
    timestamp: float = field(default_factory=time.time)

    # FPS
    fps: float = 0.0
    frame_count: int = 0

    # Thermal
    cpu_temp: float = 0.0
    gpu_temp: float = 0.0

    # Memory
    memory_percent: float = 0.0
    swap_percent: float = 0.0

    # Throttle
    throttle_status: str = "Unknown"
    throttle_raw: str = "0x0"

    # Model info
    active_model: str = "none"
    backend_name: str = "none"
    model_tier: int = -1
    vram_mb: int = 0

    # Control plane (filled by the controller)
    state: str = "NOMINAL"
    rung: int = 0
    rung_name: str = ""
    detections: int = 0
    swap_stall_ms: float = 0.0
    input_fault: str = ""

    # Platform
    platform: str = "unknown"

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, data: str) -> "HealthSnapshot":
        """Deserialize from JSON string."""
        return cls(**json.loads(data))

    def to_dict(self) -> dict:
        """Convert to plain dict."""
        return asdict(self)
