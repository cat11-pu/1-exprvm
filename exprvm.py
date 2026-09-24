"""exprvm.py：表达式引擎。

老入口 evaluate 保持累加语义（老规则在用）；
新增 compile_expression/run：中缀表达式编译为指令序列再执行，
支持优先级、括号、一元正负号、比较运算与 and/or 短路求值。
"""
from __future__ import annotations

import re


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


class Code(list):
    """指令序列：list 子类，附带最近一次 run 的短路统计。"""

    def __init__(self, *args):
        super().__init__(*args)
        self.skipped = 0


_TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<num>\d+)"
    r"|(?P<name>[A-Za-z_]\w*)"
    r"|(?P<op>==|!=|<=|>=|&&|\|\||[-+*/()<>])"
    r")"
)

_CMP_OPS = {"==", "!=", "<", ">", "<=", ">="}


def _tokenize(text: str) -> list:
    tokens = []
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        match = _TOKEN_RE.match(text, pos)
        if match is None:
            raise ExprError("非法字符 %r" % text[pos])
        pos = match.end()
        kind = match.lastgroup
        value = match.group()
        if kind == "num":
            tokens.append(("num", int(value)))
        else:
            tokens.append((kind, value))
    return tokens


class _Parser:
    """优先级（低到高）：or < and < 比较 < 加减 < 乘除 < 一元正负 < 原子。"""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.code = Code()

    def _peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _advance(self):
        tok = self._peek()
        self.pos += 1
        return tok

    def _emit(self, *instr):
        self.code.append(instr)

    def parse(self) -> Code:
        self._parse_or()
        if self.pos != len(self.tokens):
            raise ExprError("表达式有多余的内容")
        return self.code

    def _parse_or(self):
        self._parse_and()
        while True:
            tok = self._peek()
            if tok and (tok[1] == "or" or tok[1] == "||"):
                self._advance()
                jump_at = len(self.code)
                self._emit("jmpt", None)
                self._parse_and()
                self._emit("or")
                self.code[jump_at] = ("jmpt", len(self.code))
            else:
                return

    def _parse_and(self):
        self._parse_cmp()
        while True:
            tok = self._peek()
            if tok and (tok[1] == "and" or tok[1] == "&&"):
                self._advance()
                jump_at = len(self.code)
                self._emit("jmpf", None)
                self._parse_cmp()
                self._emit("and")
                self.code[jump_at] = ("jmpf", len(self.code))
            else:
                return

    def _parse_cmp(self):
        self._parse_add()
        while True:
            tok = self._peek()
            if tok and tok[0] == "op" and tok[1] in _CMP_OPS:
                op = tok[1]
                self._advance()
                self._parse_add()
                if op == "==":
                    self._emit("eq")
                elif op == "!=":
                    self._emit("eq")
                    self._emit("not")
                elif op == ">":
                    self._emit("gt")
                elif op == "<":
                    self._emit("lt")
                elif op == ">=":
                    self._emit("ge")
                else:
                    self._emit("le")
            else:
                return

    def _parse_add(self):
        self._parse_mul()
        while True:
            tok = self._peek()
            if tok and tok[0] == "op" and tok[1] in ("+", "-"):
                self._advance()
                self._parse_mul()
                self._emit("add" if tok[1] == "+" else "sub")
            else:
                return

    def _parse_mul(self):
        self._parse_unary()
        while True:
            tok = self._peek()
            if tok and tok[0] == "op" and tok[1] in ("*", "/"):
                self._advance()
                self._parse_unary()
                if tok[1] == "*":
                    self._emit("mul")
                else:
                    self._emit("chkdiv")
                    self._emit("div")
            else:
                return

    def _parse_unary(self):
        tok = self._peek()
        if tok and tok[0] == "op" and tok[1] == "-":
            self._advance()
            self._parse_unary()
            self._emit("neg")
        elif tok and tok[0] == "op" and tok[1] == "+":
            self._advance()
            self._parse_unary()
            self._emit("pos")
        else:
            self._parse_atom()

    def _parse_atom(self):
        tok = self._advance()
        if tok is None:
            raise ExprError("表达式不完整")
        kind, value = tok[0], tok[1]
        if kind == "num":
            self._emit("const", value)
        elif kind == "name":
            if value in ("and", "or"):
                raise ExprError("运算符 %s 位置错误" % value)
            self._emit("load", value)
        elif value == "(":
            self._emit("nop")
            self._parse_or()
            closing = self._advance()
            if closing is None or closing[1] != ")":
                raise ExprError("括号未闭合")
            self._emit("nop")
        else:
            raise ExprError("无法解析 %r" % (value,))


def compile_expression(text: str) -> Code:
    """把中缀表达式编译成指令序列（含优先级、括号、一元正负号）。"""
    return _Parser(_tokenize(text)).parse()


def run(code, scope=None) -> int:
    """执行 compile_expression 生成的指令序列。"""
    values = scope if scope is not None else {}
    stack = []
    if isinstance(code, Code):
        code.skipped = 0
    ip = 0
    while ip < len(code):
        instr = code[ip]
        op = instr[0]
        if op == "const":
            stack.append(instr[1])
        elif op == "load":
            name = instr[1]
            if name not in values:
                raise ExprError("未定义变量 %s" % name)
            stack.append(values[name])
        elif op == "nop":
            pass
        elif op == "neg":
            stack.append(-stack.pop())
        elif op == "pos":
            stack.append(+stack.pop())
        elif op == "not":
            stack.append(0 if stack.pop() else 1)
        elif op == "chkdiv":
            if not stack or stack[-1] == 0:
                raise ExprError("除数为零")
        elif op in ("add", "sub", "mul", "div", "eq", "gt", "lt", "ge", "le", "and", "or"):
            right = stack.pop()
            left = stack.pop()
            if op == "add":
                stack.append(left + right)
            elif op == "sub":
                stack.append(left - right)
            elif op == "mul":
                stack.append(left * right)
            elif op == "div":
                if right == 0:
                    raise ExprError("除数为零")
                stack.append(left // right)
            elif op == "eq":
                stack.append(1 if left == right else 0)
            elif op == "gt":
                stack.append(1 if left > right else 0)
            elif op == "lt":
                stack.append(1 if left < right else 0)
            elif op == "ge":
                stack.append(1 if left >= right else 0)
            elif op == "le":
                stack.append(1 if left <= right else 0)
            elif op == "and":
                stack.append(1 if (left and right) else 0)
            else:
                stack.append(1 if (left or right) else 0)
        elif op == "jmpf":
            if not stack[-1]:
                target = instr[1]
                if isinstance(code, Code):
                    code.skipped += target - ip - 1
                ip = target
                continue
        elif op == "jmpt":
            if stack[-1]:
                target = instr[1]
                if isinstance(code, Code):
                    code.skipped += target - ip - 1
                ip = target
                continue
        else:
            raise ExprError("未知指令 %r" % (op,))
        ip += 1
    if not stack:
        raise ExprError("表达式没有结果")
    return stack[-1]


def short_circuit_count(code) -> int:
    """返回该指令序列最近一次 run 中被短路跳过的指令数。"""
    return getattr(code, "skipped", 0)


def locate(text: str) -> int:
    """返回表达式出错位置：合法表达式返回 0，否则返回出错位置（表达式结尾）。"""
    try:
        compile_expression(text)
    except ExprError:
        return len(text)
    return 0
