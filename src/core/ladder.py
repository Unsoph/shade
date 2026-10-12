"""The degradation ladder: ordered rungs from best (0) to emergency.

A rung is a complete operating point: which model, at what input size,
how often detection runs, and on which backend. Moving between rungs that
share a model is free; moving between models needs a preload.
"""

import logging
import os
from dataclasses import dataclass, field

from src.core.config import resolve_path

logger = logging.getLogger(__name__)
MB = 1024 * 1024


@dataclass(frozen=True)
class Rung:
    name: str
    model: str
    input_size: int
    detect_every: int = 1
    threads: int | None = None
    backend: str = "onnxruntime"
    options: dict = field(default_factory=dict, hash=False, compare=False)

    def same_model(self, other: "Rung") -> bool:
        """True when switching to `other` needs no model reload."""
        return (self.model, self.input_size, self.threads, self.backend,
                tuple(sorted(self.options.items()))) == (
                other.model, other.input_size, other.threads, other.backend,
                tuple(sorted(other.options.items())))

    def model_path(self) -> str:
        return str(resolve_path(self.model))

    def size_mb(self) -> float:
        path = self.model_path()
        return os.path.getsize(path) / MB if os.path.isfile(path) else 0.0


def parse_ladder(config: dict) -> list[Rung]:
    """Build rungs from config['ladder']; unspecified fields inherit
    from config['inference']."""
    inf = config["inference"]
    rungs = []
    for i, item in enumerate(config["ladder"]):
        try:
            rungs.append(Rung(
                name=item["name"],
                model=item["model"],
                input_size=int(item.get("input_size", inf["input_size"])),
                detect_every=max(1, int(item.get("detect_every", 1))),
                threads=item.get("threads", inf["num_threads"]),
                backend=item.get("backend", inf["backend"]),
                options=dict(item.get("options", {})),
            ))
        except KeyError as exc:
            raise ValueError(f"ladder[{i}] is missing {exc}") from exc
    return rungs


def available_rungs(rungs: list[Rung]) -> list[Rung]:
    """Keep rungs whose model file exists (the fake backend needs none)."""
    keep = []
    for rung in rungs:
        if rung.backend == "fake" or os.path.isfile(rung.model_path()):
            keep.append(rung)
        else:
            logger.info("Ladder: skipping '%s' (missing %s)", rung.name, rung.model)
    return keep
