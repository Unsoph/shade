"""Configuration loading: YAML file merged over built-in defaults.

All tunables live in config/deployment.yaml (and defaults.py for keys the
file omits). Code reads values from the merged dict; it never hard-codes
thresholds.
"""

import copy
import logging
from pathlib import Path

import yaml

from src.core.defaults import DEFAULTS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


def resolve_path(path: str | Path) -> Path:
    """Resolve a config path relative to the project root, not the CWD."""
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def deep_merge(base: dict, override: dict) -> dict:
    """Return base with override merged in recursively (inputs untouched)."""
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_config(path: str | Path | None = None) -> dict:
    """Load YAML config merged over DEFAULTS. Raises FileNotFoundError."""
    cfg_path = resolve_path(path or "config/deployment.yaml")
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with open(cfg_path, "r") as f:
        user = yaml.safe_load(f) or {}
    return deep_merge(DEFAULTS, user)


def setup_logging(config: dict) -> None:
    """Configure root logging from the logging section."""
    log_cfg = config["logging"]
    logging.basicConfig(
        level=getattr(logging, log_cfg["level"]),
        format=log_cfg["format"],
    )
