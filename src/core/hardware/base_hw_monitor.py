"""Abstract base class for hardware monitors.

Every hardware monitor (Pi, Jetson, generic Linux) implements this
contract. Nothing outside hardware/ imports a monitor directly —
everything goes through hw_factory.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThrottleFlags:
    """Parsed throttle state — Pi-specific but interface is universal.

    On non-Pi hardware, all flags default to False and raw_hex = "0x0".
    """

    undervoltage: bool = False
    freq_capped: bool = False
    throttled: bool = False
    undervoltage_occurred: bool = False
    freq_capped_occurred: bool = False
    throttled_occurred: bool = False
    raw_hex: str = "0x0"

    @property
    def is_clean(self) -> bool:
        return self.raw_hex == "0x0"

    @property
    def human_readable(self) -> str:
        """Plain English throttle status for the dashboard."""
        if self.is_clean:
            return "Clean"
        parts = []
        if self.throttled:
            parts.append("Thermally throttled")
        if self.freq_capped:
            parts.append("Freq capped")
        if self.undervoltage:
            parts.append("Undervoltage")
        if not parts:
            # Only historical flags set
            hist = []
            if self.throttled_occurred:
                hist.append("throttle")
            if self.freq_capped_occurred:
                hist.append("freq cap")
            if self.undervoltage_occurred:
                hist.append("undervolt")
            return f"Previously: {', '.join(hist)}"
        return " | ".join(parts)


class HardwareMonitor(ABC):
    """Contract for hardware monitoring backends."""

    @abstractmethod
    def get_cpu_temp(self) -> float:
        """CPU temperature in Celsius."""

    @abstractmethod
    def get_gpu_temp(self) -> float:
        """GPU temperature in Celsius.

        On Pi, this mirrors cpu_temp (no discrete GPU).
        """

    @abstractmethod
    def get_memory_percent(self) -> float:
        """System memory usage as percentage [0, 100]."""

    def get_cpu_util(self) -> float:
        """Mean CPU utilisation over all cores, 0..1 (psutil by default)."""
        import psutil
        return psutil.cpu_percent(interval=None) / 100.0

    @abstractmethod
    def get_swap_percent(self) -> float:
        """Swap usage as percentage [0, 100].

        On Pi, swap > 10% is a warning (SD card swap is 10-50x slower).
        """

    @abstractmethod
    def get_throttle_flags(self) -> ThrottleFlags:
        """Current throttle/power state.

        On non-Pi hardware, returns a clean ThrottleFlags.
        """

    @abstractmethod
    def get_platform_name(self) -> str:
        """Human-readable platform identifier."""
