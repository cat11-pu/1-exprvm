"""rules.py：规则引擎（老入口 evaluate 不能改）。"""
from __future__ import annotations

from exprvm import compile_expression, evaluate, run


class RuleEngine:
    def __init__(self):
        self.scope = {}

    def set(self, name, value):
        self.scope[name] = value

    def check(self, text: str) -> int:
        """老接口：按累加语义算（兼容保留）。"""
        return evaluate(text)

    def check_all(self, texts) -> list:
        """批量编译并执行表达式。"""
        return [run(compile_expression(text), self.scope) for text in texts]
