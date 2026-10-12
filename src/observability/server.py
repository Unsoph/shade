"""Tiny read-only HTTP server (stdlib only) for status, metrics and history.

Binds to 127.0.0.1 by default: the endpoints are unauthenticated, so
exposing them beyond localhost is an explicit config choice.

  /            live HTML page
  /status      current health snapshot (JSON)
  /decisions   recent audit-log events (JSON, newest first)
  /metrics     Prometheus text format
  /healthz     200 "ok"
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from src.observability.metrics import render
from src.observability.page import PAGE

logger = logging.getLogger(__name__)
KINDS = ("decision", "swap_done", "swap_failed", "camera_reconnect",
         "camera_reopen_requested", "child_started", "child_restart",
         "supervisor_gave_up")


def make_handler(health, log, limit: int):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: str, ctype: str, code: int = 200):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802 - http.server API
            url = urlparse(self.path)
            if url.path == "/":
                self._send(PAGE, "text/html")
            elif url.path == "/status":
                self._send(json.dumps(health.snapshot().to_dict()),
                           "application/json")
            elif url.path == "/decisions":
                q = parse_qs(url.query)
                n = min(int(q.get("limit", [limit])[0]), 1000)
                kind = q.get("kind", [None])[0]
                self._send(json.dumps(log.recent(n, kind)), "application/json")
            elif url.path == "/metrics":
                counts = {k: log.count(k) for k in KINDS if log.count(k)}
                self._send(render(health.snapshot().to_dict(), counts),
                           "text/plain; version=0.0.4")
            elif url.path == "/healthz":
                self._send("ok\n", "text/plain")
            else:
                self._send("not found\n", "text/plain", 404)

        def log_message(self, fmt, *args):  # keep the console quiet
            logger.debug("http: " + fmt, *args)

    return Handler


class ObservabilityServer:
    def __init__(self, health, log, host: str = "127.0.0.1", port: int = 9108,
                 limit: int = 50):
        self._httpd = ThreadingHTTPServer((host, port),
                                          make_handler(health, log, limit))
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        name="observability", daemon=True)

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    def start(self) -> "ObservabilityServer":
        self._thread.start()
        logger.info("Observability on http://%s:%d/",
                    self._httpd.server_address[0], self.port)
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
