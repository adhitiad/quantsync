"""
health_status.py — Fixed Version
Fix #2: Split endpoint liveness vs readiness.

MASALAH SEBELUMNYA:
  is_ready() = db_ready AND runtime_data_ready AND grpc_ready
  → Jika warmup timeout, runtime_data_ready tetap False
  → /health selalu 503
  → docker-compose menunggu quantsync-ai-engine healthy selamanya
  → quantsync-gateway tidak pernah naik (deadlock)

SOLUSI:
  /health  → is_alive()  → hanya cek db_ready + grpc_ready
             Dipakai oleh Docker Compose healthcheck
             Tidak bergantung pada data warmup

  /ready   → is_ready()  → cek semua termasuk runtime_data_ready
             Dipakai oleh gateway sebelum mulai route traffic
             (opsional — bisa di-poll dari gateway sebelum kirim sinyal)
"""

import threading
from typing import TypedDict


class HealthState(TypedDict):
    db_ready: bool
    runtime_data_ready: bool
    grpc_ready: bool


class RuntimeHealth:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: HealthState = {
            "db_ready": False,
            "runtime_data_ready": False,
            "grpc_ready": False,
        }

    def set(self, key: str, value: bool) -> None:
        with self._lock:
            if key not in self._state:
                raise KeyError(f"Unknown health key: '{key}'")
            self._state[key] = value  # type: ignore[literal-required]

    def snapshot(self) -> HealthState:
        with self._lock:
            return dict(self._state)  # type: ignore[return-value]

    def is_alive(self) -> bool:
        """
        Liveness check — untuk Docker Compose healthcheck.
        True jika DB dan gRPC server sudah siap menerima koneksi.
        Tidak bergantung pada apakah data market sudah ter-ingest.
        """
        state = self.snapshot()
        return state["db_ready"] and state["grpc_ready"]

    def is_ready(self) -> bool:
        """
        Readiness check — untuk gateway atau load balancer.
        True jika SEMUA komponen siap termasuk data warmup.
        """
        state = self.snapshot()
        return state["db_ready"] and state["runtime_data_ready"] and state["grpc_ready"]


runtime_health = RuntimeHealth()
