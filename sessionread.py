"""sessionread.py：一致性读（基线：随便挑副本）。"""
from __future__ import annotations


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
        raise NotImplementedError("会话粘滞还没实现")

    def read(self, client: str, required: int = 0) -> dict:
        """基线：按名字挑第一个副本，不看落后多少。"""
        if not self.replicas:
            return {"node": None, "applied": None}
        node = sorted(self.replicas)[0]
        return {"node": node, "applied": self.replicas[node]}

    def recover(self) -> dict:
        raise NotImplementedError("重启恢复还没实现")

    def stats(self) -> dict:
        return {"replicas": dict(self.replicas), "sticky": dict(self.sticky),
                "switches": self.switches, "stale": self.stale, "max_lag": self.max_lag}
