"""Prometheus text exposition (format 0.0.4) built from a health snapshot."""

STATES = ["NOMINAL", "ELEVATED", "DEGRADED", "CRITICAL", "RECOVERING",
          "POWER_WARNING", "OS_CONTENTION", "FAULT"]

# (metric, help, type, snapshot field)
GAUGES = [
    ("shade_fps", "Output frames per second", "gauge", "fps"),
    ("shade_frames_total", "Frames processed", "counter", "frame_count"),
    ("shade_cpu_temp_celsius", "CPU temperature", "gauge", "cpu_temp"),
    ("shade_memory_percent", "RAM used percent", "gauge", "memory_percent"),
    ("shade_swap_percent", "Swap used percent", "gauge", "swap_percent"),
    ("shade_rung", "Active ladder rung (0 = best)", "gauge", "rung"),
    ("shade_detections", "Detections in the last frame", "gauge", "detections"),
    ("shade_swap_stall_milliseconds", "Last model swap stall", "gauge",
     "swap_stall_ms"),
    ("shade_model_memory_mb", "Memory attributed to the loaded model", "gauge",
     "vram_mb"),
]


def render(snap: dict, event_counts: dict[str, int]) -> str:
    """Render snapshot dict + event counts as Prometheus text."""
    lines = []
    for name, helptext, kind, key in GAUGES:
        lines += [f"# HELP {name} {helptext}", f"# TYPE {name} {kind}",
                  f"{name} {float(snap.get(key, 0) or 0):g}"]
    lines += ["# HELP shade_state Current state (1 = active)",
              "# TYPE shade_state gauge"]
    current = snap.get("state", "")
    lines += [f'shade_state{{state="{s}"}} {int(s == current)}' for s in STATES]
    lines += ["# HELP shade_input_fault 1 when the camera input is unhealthy",
              "# TYPE shade_input_fault gauge",
              f"shade_input_fault {int(bool(snap.get('input_fault')))}",
              "# HELP shade_events_total Audit-log events by kind",
              "# TYPE shade_events_total counter"]
    lines += [f'shade_events_total{{kind="{k}"}} {v}'
              for k, v in sorted(event_counts.items())]
    return "\n".join(lines) + "\n"
