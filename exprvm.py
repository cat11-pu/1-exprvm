"""exprvm.py：表达式引擎（基线：从左往右累加，没有编译与作用域）。"""
from __future__ import annotations


class ExprError(ValueError):
    pass


def evaluate(text: str, scope=None) -> int:
    """老入口：按空格切分后从左往右累加（老规则在用它）。"""
    total = 0
    for piece in text.split():
        try:
            total += int(piece)
        except ValueError:
            raise ExprError("无法解析 %s" % piece)
    return total


def compile_expression(text: str) -> list:
    raise NotImplementedError("编译还没实现")


def run(code: list, scope=None) -> int:
    raise NotImplementedError("字节码执行还没实现")
