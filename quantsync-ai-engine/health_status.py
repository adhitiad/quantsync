import threading


class RuntimeHealth:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = {
            "db_ready": False,
            "runtime_data_ready": False,
            "grpc_ready": False,
        }

    def set(self, key, value):
        with self._lock:
            self._state[key] = value

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def is_ready(self):
        state = self.snapshot()
        return state["db_ready"] and state["runtime_data_ready"] and state["grpc_ready"]


runtime_health = RuntimeHealth()
