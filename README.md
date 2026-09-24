# exprvm

纯 Python 标准库的 exprvm（无第三方依赖）。

## 用法

    import exprvm

    code = exprvm.compile_expression("a + 3 * 4")  # 编译为指令序列
    exprvm.run(code, {"a": 2})                     # 执行 -> 14
    exprvm.short_circuit_count(code)               # 最近一次 run 短路跳过的指令数
    exprvm.locate("a + ")                          # 出错位置 -> 4

支持运算符优先级、括号、一元正负号、比较运算与 `and`/`or` 短路求值；
除零与未定义变量会抛出 `ExprError`。
老入口 `evaluate` 与 `rules.RuleEngine.check` 保持累加语义不变。

## 测试

    python3 -m unittest discover -s tests -v

## 场景自检

    python3 check_sample.py
