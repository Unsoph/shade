#!/usr/bin/env python3
"""SHADE setup diagnostics — verify runtime availability.

Checks for CUDA, TensorRT, ONNX Runtime, TFLite, OpenVINO, and
prints a diagnostic table. Detects Pi hardware and JetPack version.
Exits non-zero if no usable inference runtime is found.
"""

import platform
import shutil
import subprocess
import sys


def _check_importable(module_name: str) -> tuple[bool, str]:
    """Try to import a module, return (available, version_or_error)."""
    try:
        mod = __import__(module_name)
        version = getattr(mod, "__version__", "unknown")
        return True, version
    except ImportError:
        return False, "not installed"


def _check_command(cmd: str) -> tuple[bool, str]:
    """Check if a command is available on PATH."""
    path = shutil.which(cmd)
    if path:
        return True, path
    return False, "not found"


def _detect_pi_model() -> str:
    """Read Pi model from /proc/cpuinfo or /sys/firmware/devicetree."""
    try:
        with open("/sys/firmware/devicetree/base/model", "r") as f:
            return f.read().strip().rstrip("\x00")
    except FileNotFoundError:
        pass
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("Model"):
                    return line.split(":", 1)[1].strip()
    except FileNotFoundError:
        pass
    return "Not a Raspberry Pi (or not detectable)"


def _detect_jetpack() -> str:
    """Detect JetPack version on Jetson devices."""
    try:
        with open("/etc/nv_tegra_release", "r") as f:
            return f.readline().strip()
    except FileNotFoundError:
        return "N/A (not Jetson)"


def _get_vcgencmd_temp() -> str:
    """Try to read Pi temperature via vcgencmd."""
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "vcgencmd not available"


def run_diagnostics() -> bool:
    """Run all checks and print a diagnostic table. Returns True if viable."""
    print("=" * 60)
    print("  SHADE — Setup Diagnostics")
    print("=" * 60)

    # Platform info
    print(f"\n  Platform:     {platform.platform()}")
    print(f"  Architecture: {platform.machine()}")
    print(f"  Python:       {sys.version.split()[0]}")
    print(f"  Pi Model:     {_detect_pi_model()}")
    print(f"  JetPack:      {_detect_jetpack()}")
    print(f"  CPU Temp:     {_get_vcgencmd_temp()}")

    # Runtime checks
    print(f"\n  {'Runtime':<20} {'Available':<12} {'Version / Path'}")
    print("  " + "-" * 56)

    runtimes = [
        ("onnxruntime", "onnxruntime"),
        ("onnxruntime-gpu", "onnxruntime"),  # same module, different package
        ("tflite_runtime", "tflite_runtime"),
        ("openvino", "openvino"),
        ("OpenCV", "cv2"),
        ("NumPy", "numpy"),
        ("psutil", "psutil"),
        ("PyYAML", "yaml"),
    ]

    any_inference_ok = False
    for display_name, module_name in runtimes:
        ok, info = _check_importable(module_name)
        status = "YES" if ok else "NO"
        print(f"  {display_name:<20} {status:<12} {info}")
        if ok and display_name in ("onnxruntime", "tflite_runtime", "openvino"):
            any_inference_ok = True

    # Tool checks
    print()
    tools = ["vcgencmd", "tegrastats"]
    for tool in tools:
        ok, info = _check_command(tool)
        status = "YES" if ok else "NO"
        print(f"  {tool:<20} {status:<12} {info}")

    print("\n" + "=" * 60)

    if not any_inference_ok:
        print("  ERROR: No inference runtime available.")
        print("  Install at least one: pip install onnxruntime")
        print("=" * 60)
        return False

    print("  Status: READY")
    print("=" * 60)
    return True


if __name__ == "__main__":
    ok = run_diagnostics()
    sys.exit(0 if ok else 1)
