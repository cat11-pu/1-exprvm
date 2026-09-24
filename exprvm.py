"""exprvm.py：表达式引擎。

- evaluate：老入口，按空格切分从左往右累加（老规则在用，不能改）。
- compile_expression：把中缀表达式编译成指令序列（优先级、括号、一元正负号）。
- run：执行指令序列（乘除优先于加减、括号优先、and/or 短路求值）。
- short_circuit_count：某段指令最近一次 run 时被短路跳过的指令数。
- locate：表达式出错位置（出错给结尾位置，无错给 0）。
"""
from __future__ import annotations


class ExprError(ValueError):
    pass


class Code(list):
    """指令序列；skipped 记录最近一次 run 被短路跳过的指令数。"""

    def __init__(self, instructions=()):
        super().__init__(instructions)
        self.skipped = 0


def evaluate(text: str, scope=None) -> int:
    """老入口：按空格切分后从左往右累加（老规则在用它）。"""
    total = 0
    for piece in text.split():
        try:
            total += int(piece)
        except ValueError:
            raise ExprError("无法解析 %s" % piece)
    return total


_TWO_CHAR_OPS = (">=", "<=", "==", "!=")
_ONE_CHAR_OPS = "+-*/()><"


def _tokenize(text):
    tokens = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch.isdigit():
            j = i + 1
            while j < len(text) and text[j].isdigit():
                j += 1
            tokens.append(("NUM", int(text[i:j])))
            i = j
        elif ch.isalpha() or ch == "_":
            j = i + 1
            while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            if word in ("and", "or"):
                tokens.append((word.upper(), word))
            else:
                tokens.append(("NAME", word))
            i = j
        elif text[i:i + 2] in _TWO_CHAR_OPS:
            tokens.append(("OP", text[i:i + 2]))
            i += 2
        elif ch in _ONE_CHAR_OPS:
            tokens.append(("OP", ch))
            i += 1
        else:
            raise ExprError("非法字符 %r（位置 %d）" % (ch, i))
    tokens.append(("END", None))
    return tokens


_CMP_OPS = {">": "GT", "<": "LT", ">=": "GE", "<=": "LE", "==": "EQ"}


class _Parser:
    """递归下降编译：or -> and -> 比较 -> 加减 -> 乘除 -> 一元 -> 原子。"""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.code = []

    def _kind(self):
        return self.tokens[self.pos][0]

    def _value(self):
        return self.tokens[self.pos][1]

    def _advance(self):
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _emit(self, *instruction):
        self.code.append(instruction)

    def _emit_jump(self, op):
        self._emit(op, 0)
        return len(self.code) - 1

    def _patch(self, index):
        self.code[index] = (self.code[index][0], len(self.code))

    def parse(self):
        self._parse_or()
        if self._kind() != "END":
            raise ExprError("表达式里有多余内容")
        return self.code

    def _parse_or(self):
        self._parse_and()
        while self._kind() == "OR":
            self._advance()
            jump = self._emit_jump("JUMP_IF_TRUE")
            self._emit("POP")
            self._parse_and()
            self._patch(jump)

    def _parse_and(self):
        self._parse_cmp()
        while self._kind() == "AND":
            self._advance()
            jump_false = self._emit_jump("JUMP_IF_FALSE")
            self._parse_cmp()
            jump_end = self._emit_jump("JUMP")
            self._patch(jump_false)
            self._emit("LOAD_CONST", 0)
            self._patch(jump_end)

    def _parse_cmp(self):
        self._parse_add()
        while self._kind() == "OP" and self._value() in (">", "<", ">=", "<=", "==", "!="):
            op = self._advance()[1]
            self._parse_add()
            if op == "!=":  # != 用 EQ + NOT 组合
                self._emit("EQ")
                self._emit("NOT")
            else:
                self._emit(_CMP_OPS[op])

    def _parse_add(self):
        self._parse_mul()
        while self._kind() == "OP" and self._value() in ("+", "-"):
            op = self._advance()[1]
            self._parse_mul()
            self._emit("ADD" if op == "+" else "SUB")

    def _parse_mul(self):
        self._parse_unary()
        while self._kind() == "OP" and self._value() in ("*", "/"):
            op = self._advance()[1]
            self._parse_unary()
            self._emit("MUL" if op == "*" else "DIV")

    def _parse_unary(self):
        if self._kind() == "OP" and self._value() in ("+", "-"):
            op = self._advance()[1]
            self._parse_unary()
            self._emit("POS" if op == "+" else "NEG")
        else:
            self._parse_primary()

    def _parse_primary(self):
        kind, value = self._kind(), self._value()
        if kind == "NUM":
            self._advance()
            self._emit("LOAD_CONST", value)
        elif kind == "NAME":
            self._advance()
            self._emit("LOAD_VAR", value)
        elif kind == "OP" and value == "(":
            self._advance()
            self._emit("GROUP_BEGIN")  # 括号占位指令，保留结构
            self._parse_or()
            if not (self._kind() == "OP" and self._value() == ")"):
                raise ExprError("缺少右括号")
            self._advance()
            self._emit("GROUP_END")
        else:
            raise ExprError("表达式不完整")


def compile_expression(text: str) -> Code:
    """把中缀表达式编译成指令序列。"""
    return Code(_Parser(_tokenize(text)).parse())


def run(code, scope=None) -> int:
    """执行指令序列；除零与未定义变量抛 ExprError。"""
    scope = scope or {}
    stack = []
    skipped = 0
    pc = 0
    while pc < len(code):
        instruction = code[pc]
        op = instruction[0]
        if op == "LOAD_CONST":
            stack.append(instruction[1])
        elif op == "LOAD_VAR":
            name = instruction[1]
            if name not in scope:
                raise ExprError("未定义变量 %s" % name)
            stack.append(scope[name])
        elif op in ("ADD", "SUB", "MUL", "DIV"):
            right = stack.pop()
            left = stack.pop()
            if op == "ADD":
                stack.append(left + right)
            elif op == "SUB":
                stack.append(left - right)
            elif op == "MUL":
                stack.append(left * right)
            else:
                if right == 0:
                    raise ExprError("除零")
                stack.append(left // right)
        elif op in ("GT", "LT", "GE", "LE", "EQ"):
            right = stack.pop()
            left = stack.pop()
            if op == "GT":
                hit = left > right
            elif op == "LT":
                hit = left < right
            elif op == "GE":
                hit = left >= right
            elif op == "LE":
                hit = left <= right
            else:
                hit = left == right
            stack.append(1 if hit else 0)
        elif op == "NOT":
            stack.append(0 if stack.pop() else 1)
        elif op == "NEG":
            stack.append(-stack.pop())
        elif op == "POS":
            stack.append(+stack.pop())
        elif op == "POP":
            stack.pop()
        elif op == "JUMP":
            pc = instruction[1]
            continue
        elif op == "JUMP_IF_FALSE":
            if not stack.pop():
                skipped += instruction[1] - pc - 1
                pc = instruction[1]
                continue
        elif op == "JUMP_IF_TRUE":
            if stack[-1]:
                skipped += instruction[1] - pc - 1
                pc = instruction[1]
                continue
            stack.pop()
        elif op in ("GROUP_BEGIN", "GROUP_END"):
            pass
        else:
            raise ExprError("未知指令 %r" % (op,))
        pc += 1
    if hasattr(code, "skipped"):
        code.skipped = skipped
    if not stack:
        raise ExprError("表达式没有结果")
    return stack[-1]


def short_circuit_count(code) -> int:
    """某段指令最近一次 run 时被 and/or 短路跳过的指令数。"""
    return getattr(code, "skipped", 0)


def locate(text) -> int:
    """表达式出错位置：出错给结尾位置，没出错给 0。"""
    try:
        compile_expression(text)
    except ExprError:
        return len(text)
    return 0
