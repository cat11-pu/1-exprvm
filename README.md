# exprvm

纯 Python 标准库的 exprvm（无第三方依赖）。

## 用法

    import exprvm

    code = exprvm.compile_expression("a + 3 * 4")
    exprvm.run(code, {"a": 2})        # 14（乘除优先于加减，支持括号、一元正负号、and/or 短路）
    exprvm.short_circuit_count(code)  # 最近一次 run 被短路跳过的指令数
    exprvm.locate("a + ")             # 出错位置（无错为 0）

    # 老入口保持累加语义：
    exprvm.evaluate("1 2 3")          # 6

## 测试

    python3 -m unittest discover -s tests -v

## 场景自检

    python3 check_sample.py
