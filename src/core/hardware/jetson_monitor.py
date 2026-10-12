"""Jetson hardware monitor stub.

Will be implemented when migrating to Jetson hardware.
"""

from src.core.hardware.base_hw_monitor import HardwareMonitor, ThrottleFlags


class JetsonMonitor(HardwareMonitor):
    """Jetson monitor (not yet implemented)."""

    def get_cpu_temp(self) -> float:
        raise NotImplementedError("Jetson monitor requires Jetson hardware.")

    def get_gpu_temp(self) -> float:
        raise NotImplementedError("Jetson monitor requires Jetson hardware.")

    def get_memory_percent(self) -> float:
        raise NotImplementedError("Jetson monitor requires Jetson hardware.")

    def get_swap_percent(self) -> float:
        raise NotImplementedError("Jetson monitor requires Jetson hardware.")

    def get_throttle_flags(self) -> ThrottleFlags:
        raise NotImplementedError("Jetson monitor requires Jetson hardware.")

    def get_platform_name(self) -> str:
        return "Jetson (stub)"
