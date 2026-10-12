"""Hardware monitor factory.

Creates the correct HardwareMonitor based on deployment.yaml config.
Falls back to a generic monitor using psutil when platform-specific
tools are unavailable.
"""

import logging

from src.core.hardware.base_hw_monitor import HardwareMonitor, ThrottleFlags

logger = logging.getLogger(__name__)


class GenericMonitor(HardwareMonitor):
    """Fallback monitor using psutil only — works on any platform."""

    def __init__(self):
        import psutil  # noqa: F401 — verify available
        self._logged_gpu = False

    def get_cpu_temp(self) -> float:
        import psutil
        temps = psutil.sensors_temperatures()
        if temps:
            for entries in temps.values():
                if entries:
                    return entries[0].current
        return 0.0

    def get_gpu_temp(self) -> float:
        if not self._logged_gpu:
            logger.info("Generic monitor — gpu_temp mirrors cpu_temp")
            self._logged_gpu = True
        return self.get_cpu_temp()

    def get_memory_percent(self) -> float:
        import psutil
        return psutil.virtual_memory().percent

    def get_swap_percent(self) -> float:
        import psutil
        return psutil.swap_memory().percent

    def get_throttle_flags(self) -> ThrottleFlags:
        return ThrottleFlags()  # No throttle detection on generic platforms

    def get_platform_name(self) -> str:
        return "Generic (psutil)"


def create_hw_monitor(config: dict) -> HardwareMonitor:
    """Create hardware monitor based on config.

    Args:
        config: parsed deployment.yaml dict.

    Returns:
        HardwareMonitor instance for the target platform.
    """
    hardware = config.get("device", {}).get("hardware", "generic")

    if hardware == "raspberry_pi":
        from src.core.hardware.raspberry_pi_monitor import RaspberryPiMonitor
        logger.info("Hardware monitor: Raspberry Pi")
        return RaspberryPiMonitor()
    elif hardware == "jetson":
        from src.core.hardware.jetson_monitor import JetsonMonitor
        logger.info("Hardware monitor: Jetson")
        return JetsonMonitor()
    else:
        logger.info("Hardware monitor: Generic (psutil fallback)")
        return GenericMonitor()
