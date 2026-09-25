"""sessionread.py：一致性读（粘滞会话 + 落后感知 + 快照恢复）。"""
from __future__ import annotations

import json

STATE_FILE = "sessionread_state.json"


class Reader:
    def __init__(self, max_lag: int = 3, state_file: str = STATE_FILE):
        self.max_lag = max_lag
        self.state_file = state_file
        self.replicas = {}
        self.sticky = {}
        self.switches = 0
        self.stale = 0

    def report(self, node: str, applied: int) -> dict:
        self.replicas[node] = applied
        return {"replicas": len(self.replicas)}

    def bind(self, client: str, node: str = None) -> dict:
        if node is None:
            node = self._freshest()
        if node is not None:
            self.sticky[client] = node
        return {"client": client, "node": node}

    def read(self, client: str, required: int = 0) -> dict:
        if not self.replicas:
            return {"node": None, "applied": None}
        node = self.sticky.get(client)
        if node is None or node not in self.replicas:
            node = self._freshest()
            self.sticky[client] = node
        elif self.replicas[node] < required:
            candidate = self._switch_candidate(required)
            if candidate is not None and candidate != node:
                node = candidate
                self.sticky[client] = node
                self.switches += 1
        applied = self.replicas[node]
        if self._latest() - applied > self.max_lag:
            self.stale += 1
        return {"node": node, "applied": applied}

    def persist(self) -> dict:
        blob = {"max_lag": self.max_lag, "replicas": dict(self.replicas),
                "sticky": dict(self.sticky), "switches": self.switches,
                "stale": self.stale}
        with open(self.state_file, "w", encoding="utf-8") as fh:
            json.dump(blob, fh)
        return blob

    def restore(self, blob) -> dict:
        if isinstance(blob, (str, bytes)):
            blob = json.loads(blob)
        self.max_lag = blob["max_lag"]
        self.replicas = dict(blob["replicas"])
        self.sticky = dict(blob["sticky"])
        self.switches = blob["switches"]
        self.stale = blob["stale"]
        return self.stats()

    def recover(self) -> dict:
        self.restore(self.persist())
        return self.stats()

    def stats(self) -> dict:
        return {"replicas": dict(self.replicas), "sticky": dict(self.sticky),
                "switches": self.switches, "stale": self.stale, "max_lag": self.max_lag}

    def _latest(self) -> int:
        return max(self.replicas.values())

    def _freshest(self):
        if not self.replicas:
            return None
        return min(self.replicas, key=lambda name: (-self.replicas[name], name))

    def _switch_candidate(self, required: int):
        latest = self._latest()
        candidates = [name for name, applied in self.replicas.items()
                      if applied >= required and latest - applied <= self.max_lag]
        if not candidates:
            return None
        return min(candidates, key=lambda name: (-self.replicas[name], name))
