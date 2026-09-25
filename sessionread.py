"""sessionread.py：会话粘滞一致性读。

策略：每个客户端首次读绑定到已应用序号最大的副本（同序号取名字最小），
之后粘在该副本上；只有当绑定副本满足不了 required 时，才允许切到
「序号 >= required 且相对最新副本落后不超过 max_lag」的副本
（按序号降序、名字升序挑选）。粘滞只换到更靠前的副本，因此同一客户端
连续读到的已应用序号单调不减。
"""
from __future__ import annotations

import json
import os

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "sessionread.state.json")


class Reader:
    def __init__(self, max_lag: int = 3):
        self.max_lag = max_lag
        self.replicas = {}
        self.sticky = {}
        self.switches = 0
        self.stale = 0

    def report(self, node: str, applied: int) -> dict:
        self.replicas[node] = applied
        return {"replicas": len(self.replicas)}

    def bind(self, client: str, node: str = None) -> dict:
        """建立会话绑定；node 为 None 时登记会话，首次读再挑副本。"""
        self.sticky[client] = node
        return {"client": client, "node": node}

    def read(self, client: str, required: int = 0) -> dict:
        if not self.replicas:
            return {"node": None, "applied": None}

        latest = max(self.replicas.values())
        bound = self.sticky.get(client)

        if bound is None or bound not in self.replicas:
            node = self._freshest()
            self.sticky[client] = node
        elif self.replicas[bound] < required:
            target = self._switch_target(required, latest)
            if target is None:
                node = bound
            else:
                node = target
                self.sticky[client] = node
                self.switches += 1
        else:
            node = bound

        applied = self.replicas[node]
        if latest - applied > self.max_lag:
            self.stale += 1
        return {"node": node, "applied": applied}

    def _freshest(self) -> str:
        """已应用序号最大的副本，同序号取名字最小。"""
        return min(self.replicas, key=lambda node: (-self.replicas[node], node))

    def _switch_target(self, required: int, latest: int):
        """序号 >= required 且落后 <= max_lag 的副本；序号降序、名字升序。"""
        candidates = [
            node for node, applied in self.replicas.items()
            if applied >= required and latest - applied <= self.max_lag
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda node: (-self.replicas[node], node))

    def snapshot(self) -> dict:
        return {
            "max_lag": self.max_lag,
            "replicas": dict(self.replicas),
            "sticky": dict(self.sticky),
            "switches": self.switches,
            "stale": self.stale,
        }

    def persist(self, path: str = STATE_PATH) -> dict:
        """把绑定关系、切换与落后计数等状态落盘。"""
        blob = self.snapshot()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(blob, handle, ensure_ascii=False)
        return blob

    def restore(self, blob) -> dict:
        """从快照（dict / JSON 字符串 / 文件对象）恢复状态。"""
        if hasattr(blob, "read"):
            blob = json.load(blob)
        elif isinstance(blob, (str, bytes, bytearray)):
            blob = json.loads(blob)
        self.max_lag = blob["max_lag"]
        self.replicas = dict(blob["replicas"])
        self.sticky = dict(blob["sticky"])
        self.switches = blob["switches"]
        self.stale = blob["stale"]
        return self.stats()

    def recover(self, path: str = STATE_PATH) -> dict:
        """模拟重启：先落盘，再从盘上恢复，状态与重启前一致。"""
        self.persist(path)
        with open(path, encoding="utf-8") as handle:
            return self.restore(handle)

    def stats(self) -> dict:
        return {"replicas": dict(self.replicas), "sticky": dict(self.sticky),
                "switches": self.switches, "stale": self.stale, "max_lag": self.max_lag}
