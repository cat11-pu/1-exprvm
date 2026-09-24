"""exprvm.py：表达式引擎。

老入口 evaluate 保持"按空格切分、从左往右累加"的语义（老规则在用，不能改）。
新入口 compile_expression / run 把中缀表达式编译成指令序列再执行：
运算符优先级、括号、一元正负号、比较运算、and/or 短路求值。

指令集（每条指令是一个元组，占序列一个位置）：
    ("push", 值)              压入整数常量
    ("load", 名)              压入作用域变量（未定义则报错）
    ("neg",) / ("pos",)       一元负号 / 正号
    ("add"/"sub"/"mul"/"div",)  加减乘除（除零报错）
    ("eq"/"gt"/"lt"/"ge"/"le",)  比较，压入 1 或 0（!= 编译为 eq + not）
    ("not",)                  逻辑取反，压入 1 或 0
    ("enter",) / ("leave",)   括号分组标记，执行时是空操作
    ("pop",)                  丢弃栈顶
    ("jump_if_false", 目标)   弹出栈顶，为假则跳转（目标处的 push 0 给出结果）
    ("jump_if_true", 目标)    栈顶为真则跳转并保留栈顶作为结果，为假则继续
    ("jump", 目标)            无条件跳转
"""
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


class Code(list):
    """指令序列；run 执行后会在 skipped 属性上记录短路跳过的指令数。"""

    def __init__(self, instructions=()):
        super().__init__(instructions)
        self.skipped = 0


_KEYWORDS = ("and", "or")

_COMPARE_OPS = {
    "==": (("eq",),),
    "!=": (("eq",), ("not",)),
    ">": (("gt",),),
    "<": (("lt",),),
    ">=": (("ge",),),
    "<=": (("le",),),
}


def _tokenize(text: str) -> list:
    """把表达式切成 (类别, 内容, 位置) 记号序列；非法字符抛 ExprError。"""
    tokens = []
    index = 0
    size = len(text)
    while index < size:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char.isdigit():
            end = index
            while end < size and text[end].isdigit():
                end += 1
            tokens.append(("num", int(text[index:end]), index))
            index = end
            continue
        if char.isalpha() or char == "_":
            end = index
            while end < size and (text[end].isalnum() or text[end] == "_"):
                end += 1
            tokens.append(("name", text[index:end], index))
            index = end
            continue
        pair = text[index:index + 2]
        if pair in ("==", "!=", "<=", ">="):
            tokens.append(("op", pair, index))
            index += 2
            continue
        if char in "+-*/<>()":
            tokens.append(("op", char, index))
            index += 1
            continue
        raise ExprError("非法字符 %r（位置 %d）" % (char, index))
    return tokens


class _Parser:
    """递归下降编译：or < and < 比较 < 加减 < 乘除 < 一元 < 原子。"""

    def __init__(self, text: str):
        self.tokens = _tokenize(text)
        self.index = 0
        self.code = []

    def peek(self):
        if self.index < len(self.tokens):
            return self.tokens[self.index]
        return None

    def advance(self):
        token = self.peek()
        self.index += 1
        return token

    def emit(self, *instruction):
        self.code.append(instruction)

    def at_keyword(self, word: str) -> bool:
        token = self.peek()
        return token is not None and token[0] == "name" and token[1] == word

    def parse(self) -> list:
        self.parse_or()
        if self.peek() is not None:
            raise ExprError("表达式有多余内容")
        return self.code

    def parse_or(self):
        self.parse_and()
        while self.at_keyword("or"):
            self.advance()
            hole = len(self.code)
            self.emit("jump_if_true", None)
            self.emit("pop")
            self.parse_and()
            self.code[hole] = ("jump_if_true", len(self.code))

    def parse_and(self):
        self.parse_compare()
        while self.at_keyword("and"):
            self.advance()
            hole_false = len(self.code)
            self.emit("jump_if_false", None)
            self.parse_compare()
            hole_end = len(self.code)
            self.emit("jump", None)
            self.code[hole_false] = ("jump_if_false", len(self.code))
            self.emit("push", 0)
            self.code[hole_end] = ("jump", len(self.code))

    def parse_compare(self):
        self.parse_add()
        token = self.peek()
        if token is not None and token[0] == "op" and token[1] in _COMPARE_OPS:
            self.advance()
            self.parse_add()
            for instruction in _COMPARE_OPS[token[1]]:
                self.emit(*instruction)

    def parse_add(self):
        self.parse_mul()
        while True:
            token = self.peek()
            if token is None or token[0] != "op" or token[1] not in ("+", "-"):
                return
            self.advance()
            self.parse_mul()
            self.emit("add" if token[1] == "+" else "sub")

    def parse_mul(self):
        self.parse_unary()
        while True:
            token = self.peek()
            if token is None or token[0] != "op" or token[1] not in ("*", "/"):
                return
            self.advance()
            self.parse_unary()
            self.emit("mul" if token[1] == "*" else "div")

    def parse_unary(self):
        token = self.peek()
        if token is not None and token[0] == "op" and token[1] in ("-", "+"):
            self.advance()
            self.parse_unary()
            self.emit("neg" if token[1] == "-" else "pos")
            return
        self.parse_primary()

    def parse_primary(self):
        token = self.peek()
        if token is None:
            raise ExprError("表达式不完整")
        if token[0] == "num":
            self.advance()
            self.emit("push", token[1])
            return
        if token[0] == "name":
            if token[1] in _KEYWORDS:
                raise ExprError("关键字 %r 位置不对" % token[1])
            self.advance()
            self.emit("load", token[1])
            return
        if token[0] == "op" and token[1] == "(":
            self.advance()
            self.emit("enter")
            self.parse_or()
            closing = self.peek()
            if closing is None or closing[0] != "op" or closing[1] != ")":
                raise ExprError("缺少右括号")
            self.advance()
            self.emit("leave")
            return
        raise ExprError("无法解析的记号 %r" % (token[1],))


def compile_expression(text: str) -> Code:
    """把中缀表达式编译成指令序列（优先级、括号、一元正负号、比较、短路）。"""
    return Code(_Parser(text).parse())


def run(code: list, scope=None) -> int:
    """执行 compile_expression 生成的指令序列，返回栈顶结果。"""
    if scope is None:
        scope = {}
    stack = []
    skipped = 0
    pc = 0
    size = len(code)
    while pc < size:
        instruction = code[pc]
        op = instruction[0]
        if op == "push":
            stack.append(instruction[1])
        elif op == "load":
            name = instruction[1]
            if name not in scope:
                raise ExprError("未定义变量 %s" % name)
            stack.append(scope[name])
        elif op == "neg":
            stack.append(-stack.pop())
        elif op == "pos":
            stack.append(+stack.pop())
        elif op in ("add", "sub", "mul", "div"):
            right = stack.pop()
            left = stack.pop()
            if op == "add":
                stack.append(left + right)
            elif op == "sub":
                stack.append(left - right)
            elif op == "mul":
                stack.append(left * right)
            else:
                if right == 0:
                    raise ExprError("除零错误")
                stack.append(left // right)
        elif op in ("eq", "gt", "lt", "ge", "le"):
            right = stack.pop()
            left = stack.pop()
            if op == "eq":
                hit = left == right
            elif op == "gt":
                hit = left > right
            elif op == "lt":
                hit = left < right
            elif op == "ge":
                hit = left >= right
            else:
                hit = left <= right
            stack.append(1 if hit else 0)
        elif op == "not":
            stack.append(0 if stack.pop() else 1)
        elif op in ("enter", "leave"):
            pass
        elif op == "pop":
            stack.pop()
        elif op == "jump_if_false":
            if not stack.pop():
                skipped += instruction[1] - pc - 1
                pc = instruction[1]
                continue
        elif op == "jump_if_true":
            if stack[-1]:
                skipped += instruction[1] - pc - 1
                pc = instruction[1]
                continue
        elif op == "jump":
            pc = instruction[1]
            continue
        else:
            raise ExprError("未知指令 %r" % (op,))
        pc += 1
    if not stack:
        raise ExprError("指令序列没有产生结果")
    try:
        code.skipped = skipped
    except AttributeError:
        pass
    return stack[-1]


def short_circuit_count(code: list) -> int:
    """返回该指令序列最近一次 run 时被 and/or 短路跳过的指令数（未执行过为 0）。"""
    return int(getattr(code, "skipped", 0))


def locate(text: str) -> int:
    """定位表达式出错位置：合法表达式返回 0，出错返回表达式末尾位置。"""
    try:
        compile_expression(text)
    except ExprError:
        return len(text)
    return 0
