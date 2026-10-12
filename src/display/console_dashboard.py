"""Console dashboard — rich-based live telemetry display.

Updates every 500ms. Shows FPS, temperatures, memory, swap,
throttle status, and active model info in a formatted table.
No curses — uses rich Live display.
"""

import threading
import time

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from src.core.health_monitor import HealthMonitor


def _color_temp(temp: float) -> str:
    """Color-code temperature value."""
    if temp >= 80:
        return f"[bold red]{temp:.1f}°C[/]"
    elif temp >= 65:
        return f"[yellow]{temp:.1f}°C[/]"
    elif temp > 0:
        return f"[green]{temp:.1f}°C[/]"
    return f"[dim]{temp:.1f}°C[/]"


def _color_fps(fps: float) -> str:
    """Color-code FPS value."""
    if fps >= 10:
        return f"[bold green]{fps:.1f}[/]"
    elif fps >= 5:
        return f"[yellow]{fps:.1f}[/]"
    elif fps > 0:
        return f"[red]{fps:.1f}[/]"
    return f"[dim]0.0[/]"


def _color_percent(pct: float, warn: float = 70, crit: float = 90) -> str:
    """Color-code a percentage value."""
    if pct >= crit:
        return f"[bold red]{pct:.1f}%[/]"
    elif pct >= warn:
        return f"[yellow]{pct:.1f}%[/]"
    return f"[green]{pct:.1f}%[/]"


def _color_throttle(status: str) -> str:
    """Color-code throttle status."""
    if status == "Clean":
        return f"[green]{status}[/]"
    elif "Previously" in status:
        return f"[yellow]{status}[/]"
    return f"[bold red]{status}[/]"


def _color_state(state: str) -> str:
    """Color-code the controller state."""
    if state in ("NOMINAL", "RECOVERING"):
        return f"[green]{state}[/]"
    if state in ("ELEVATED", "DEGRADED", "OS_CONTENTION"):
        return f"[yellow]{state}[/]"
    return f"[bold red]{state}[/]"


def _build_table(monitor: HealthMonitor) -> Table:
    """Build the dashboard table from current snapshot."""
    snap = monitor.snapshot()

    table = Table(
        title="[bold cyan]SHADE — Health Dashboard[/]",
        show_header=True,
        header_style="bold white",
        border_style="cyan",
        padding=(0, 1),
    )
    table.add_column("Metric", style="bold", width=18)
    table.add_column("Value", width=30)

    table.add_row("FPS", _color_fps(snap.fps))
    table.add_row("Frames", str(snap.frame_count))
    table.add_row("", "")
    table.add_row("CPU Temp", _color_temp(snap.cpu_temp))
    table.add_row("GPU Temp", _color_temp(snap.gpu_temp))
    table.add_row("Throttle", _color_throttle(snap.throttle_status))
    table.add_row("Throttle Raw", f"[dim]{snap.throttle_raw}[/]")
    table.add_row("", "")
    table.add_row("Memory", _color_percent(snap.memory_percent))
    table.add_row("Swap", _color_percent(snap.swap_percent, warn=10, crit=30))
    table.add_row("", "")
    table.add_row("State", _color_state(snap.state))
    table.add_row("Rung", f"{snap.rung} ({snap.rung_name})")
    table.add_row("Model", snap.active_model)
    table.add_row("Backend", snap.backend_name)
    table.add_row("VRAM/RAM", f"{snap.vram_mb} MB")
    table.add_row("Detections", str(snap.detections))
    table.add_row("Last swap stall", f"{snap.swap_stall_ms:.1f} ms")
    table.add_row("Input", snap.input_fault or "[green]OK[/]")
    table.add_row("", "")
    table.add_row("Platform", snap.platform)

    return table


def run_dashboard(monitor: HealthMonitor, refresh_rate: float = 0.5) -> None:
    """Run the live dashboard (blocking). Call from a dedicated thread.

    Args:
        monitor: HealthMonitor instance to read snapshots from.
        refresh_rate: seconds between display refreshes.
    """
    console = Console()
    console.print("[bold cyan]SHADE Dashboard starting...[/]\n")

    with Live(
        _build_table(monitor),
        console=console,
        refresh_per_second=int(1 / refresh_rate),
        transient=True,
    ) as live:
        try:
            while True:
                live.update(_build_table(monitor))
                time.sleep(refresh_rate)
        except KeyboardInterrupt:
            pass


def start_dashboard_thread(
    monitor: HealthMonitor, refresh_rate: float = 0.5,
) -> threading.Thread:
    """Start the dashboard in a background daemon thread."""
    t = threading.Thread(
        target=run_dashboard,
        args=(monitor, refresh_rate),
        daemon=True,
        name="dashboard",
    )
    t.start()
    return t
