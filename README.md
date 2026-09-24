# exprvm

纯 Python 标准库的 exprvm（无第三方依赖）。

## 用法

    import exprvm

    code = exprvm.compile_expression("a + 3 * 4")  # 中缀表达式编译成指令序列
    exprvm.run(code, {"a": 2})                      # 执行指令 → 14
    exprvm.short_circuit_count(code)                # and/or 短路跳过的指令数
    exprvm.locate("a + ")                           # 出错位置（合法表达式返回 0）

老入口 `exprvm.evaluate(text)` 与 `rules.RuleEngine.check(text)` 仍按
"按空格切分、从左往右累加"的语义工作（兼容保留）。

## 测试

    python3 -m unittest discover -s tests -v

## 场景自检

    python3 check_sample.py
