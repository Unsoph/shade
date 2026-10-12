"""Parse `vcgencmd get_throttled` output (pure, unit-tested)."""

from src.core.hardware.base_hw_monitor import ThrottleFlags


def parse_throttled(output: str) -> ThrottleFlags | None:
    """'throttled=0x50005' -> ThrottleFlags; None if the text is malformed."""
    try:
        hex_str = output.strip().split("=")[1].strip()
        value = int(hex_str, 16)
    except (IndexError, ValueError):
        return None
    return ThrottleFlags(
        undervoltage=bool(value & 0x1),
        freq_capped=bool(value & 0x2),
        throttled=bool(value & 0x4),
        undervoltage_occurred=bool(value & 0x10000),
        freq_capped_occurred=bool(value & 0x20000),
        throttled_occurred=bool(value & 0x40000),
        raw_hex=hex_str,
    )
