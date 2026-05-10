"""
Patch untuk health handler di server.py.
Ganti fungsi start_health_server() dengan versi ini.

Endpoint:
  GET /health  → liveness  (untuk Docker Compose healthcheck)
  GET /ready   → readiness (untuk gateway / load balancer)
  GET /status  → JSON detail semua state (untuk debugging)
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os

from health_status import runtime_health

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            # Liveness: hanya cek DB + gRPC
            # Compose healthcheck pakai ini — tidak deadlock walau warmup belum selesai
            if runtime_health.is_alive():
                self._respond(200, "ok")
            else:
                self._respond(503, "starting")

        elif self.path == "/ready":
            # Readiness: semua komponen siap termasuk data warmup
            # Gateway bisa poll ini sebelum mulai kirim traffic
            if runtime_health.is_ready():
                self._respond(200, "ready")
            else:
                self._respond(503, "warming")

        elif self.path == "/status":
            # Debug endpoint: JSON semua state
            state = runtime_health.snapshot()
            state["alive"] = runtime_health.is_alive()
            state["ready"] = runtime_health.is_ready()
            body = json.dumps(state).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self._respond(404, "not found")

    def _respond(self, code: int, body: str) -> None:
        enc = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(enc)))
        self.end_headers()
        self.wfile.write(enc)

    def log_message(self, format: str, *args: object) -> None:
        return  # suppress access logs


def start_health_server() -> None:
    port = int(os.getenv("HEALTH_PORT", "8081"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info("[Health] Server listening on :%d  (/health=liveness  /ready=readiness)", port)
    server.serve_forever()
