"""Raspberry Pi hardware monitor.

Reads CPU temp via vcgencmd (fallback: thermal_zone sysfs),
parses vcgencmd get_throttled bitmask, tracks memory and swap
via psutil.

GPU temp mirrors CPU temp on Pi — logged once at startup.
"""

import logging
import subprocess

import psutil

from src.core.hardware.base_hw_monitor import HardwareMonitor, ThrottleFlags

logger = logging.getLogger(__name__)


class RaspberryPiMonitor(HardwareMonitor):
    """Hardware monitor for Raspberry Pi (tested on Pi 5)."""

    def __init__(self):
        self._vcgencmd_available = self._check_vcgencmd()
        self._gpu_temp_logged = False

    def _check_vcgencmd(self) -> bool:
        try:
            subprocess.run(
                ["vcgencmd", "version"],
                capture_output=True, timeout=3,
            )
            logger.info("vcgencmd available — using for temp and throttle.")
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("vcgencmd not available — using sysfs/psutil fallback.")
            return False

    def get_cpu_temp(self) -> float:
        if self._vcgencmd_available:
            try:
                result = subprocess.run(
                    ["vcgencmd", "measure_temp"],
                    capture_output=True, text=True, timeout=3,
                )
                if result.returncode == 0:
                    # Parse "temp=XX.X'C"
                    text = result.stdout.strip()
                    return float(text.split("=")[1].split("'")[0])
            except (subprocess.TimeoutExpired, ValueError, IndexError):
                pass

        # Fallback: sysfs thermal zone
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return int(f.read().strip()) / 1000.0
        except (FileNotFoundError, ValueError):
            pass

        # Last resort: psutil
        temps = psutil.sensors_temperatures()
        if temps:
            for entries in temps.values():
                if entries:
                    return entries[0].current
        return 0.0

    def get_gpu_temp(self) -> float:
        """Pi has no discrete GPU — returns cpu_temp."""
        if not self._gpu_temp_logged:
            logger.info("Pi unified thermal — gpu_temp mirrors cpu_temp")
            self._gpu_temp_logged = True
        return self.get_cpu_temp()

    def get_memory_percent(self) -> float:
        return psutil.virtual_memory().percent

    def get_swap_percent(self) -> float:
        swap = psutil.swap_memory()
        return swap.percent

    def get_throttle_flags(self) -> ThrottleFlags:
        if not self._vcgencmd_available:
            return ThrottleFlags()

        try:
            result = subprocess.run(
                ["vcgencmd", "get_throttled"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                # Parse "throttled=0xN"
                hex_str = result.stdout.strip().split("=")[1]
                value = int(hex_str, 16)
                flags = ThrottleFlags(
                    undervoltage=bool(value & 0x1),
                    freq_capped=bool(value & 0x2),
                    throttled=bool(value & 0x4),
                    undervoltage_occurred=bool(value & 0x10000),
                    freq_capped_occurred=bool(value & 0x20000),
                    throttled_occurred=bool(value & 0x40000),
                    raw_hex=hex_str,
                )
                if flags.undervoltage:
                    logger.warning(
                        "HARDWARE_POWER_WARNING: undervoltage detected (%s). "
                        "Check power supply — this is a physical problem, "
                        "not a model performance issue.", hex_str,
                    )
                return flags
        except (subprocess.TimeoutExpired, ValueError, IndexError):
            pass

        return ThrottleFlags()

    def get_platform_name(self) -> str:
        return "Raspberry Pi"
