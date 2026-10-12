import json
import urllib.error
import urllib.request

from src.core.decision.log import DecisionLog
from src.core.health_monitor import HealthMonitor
from src.observability.metrics import render
from src.observability.server import ObservabilityServer


class FakeHW:
    def get_cpu_temp(self): return 61.5
    def get_gpu_temp(self): return 0.0
    def get_memory_percent(self): return 40.0
    def get_swap_percent(self): return 0.0
    def get_throttle_flags(self):
        from src.core.hardware.base_hw_monitor import ThrottleFlags
        return ThrottleFlags()
    def get_platform_name(self): return "test"


def get(server, path):
    url = f"http://127.0.0.1:{server.port}{path}"
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read().decode()


def test_render_marks_active_state():
    text = render({"state": "DEGRADED", "fps": 7.5, "rung": 2}, {"swap_done": 3})
    assert 'shade_state{state="DEGRADED"} 1' in text
    assert 'shade_state{state="NOMINAL"} 0' in text
    assert "shade_fps 7.5" in text and 'shade_events_total{kind="swap_done"} 3' in text


def test_server_endpoints():
    health = HealthMonitor(FakeHW())
    health.update()
    log = DecisionLog(":memory:")
    log.record_event("swap_done", {"to": "small-320"})
    server = ObservabilityServer(health, log, port=0).start()
    try:
        code, body = get(server, "/status")
        assert code == 200 and json.loads(body)["cpu_temp"] == 61.5
        events = json.loads(get(server, "/decisions?limit=5")[1])
        assert events[0]["kind"] == "swap_done"
        assert "shade_cpu_temp_celsius 61.5" in get(server, "/metrics")[1]
        assert get(server, "/healthz")[1] == "ok\n"
        assert "<title>SHADE</title>" in get(server, "/")[1]
        try:
            get(server, "/nope")
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.stop()
        log.close()
