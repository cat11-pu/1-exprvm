"""rules.py：规则引擎（老入口 evaluate 不能改）。"""
from __future__ import annotations

from exprvm import evaluate


class RuleEngine:
    def __init__(self):
        self.scope = {}

    def set(self, name, value):
        self.scope[name] = value

    def check(self, text: str) -> int:
        """老接口：按累加语义算（兼容保留）。"""
        return evaluate(text)

    def check_all(self, texts) -> list:
        raise NotImplementedError("批量编译执行还没实现")
