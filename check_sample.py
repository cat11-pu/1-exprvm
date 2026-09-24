"""把 sample/exprs.json 跑一遍，打印验收面（两个子系统）。"""
import json
import os
import sys

import exprvm
import rules


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join("sample", "exprs.json")
    with open(path, encoding="utf-8") as handle:
        spec = json.load(handle)
    engine = rules.RuleEngine()
    for name, value in spec["scope"].items():
        engine.set(name, value)
    rows = []
    for item in spec["exprs"]:
        code = exprvm.compile_expression(item["text"])
        rows.append((item["text"], len(code), exprvm.run(code, engine.scope)))
    print("编译后的指令数与结果 =", rows)
    print("短路求值跳过的指令数 =", [exprvm.short_circuit_count(exprvm.compile_expression(item["text"])) for item in spec["exprs"]])
    print("错误定位 =", [(item["text"], exprvm.locate(item["text"])) for item in spec["errors"]])
    print("老入口仍按累加 =", engine.check(spec["legacy"]))
    print("未定义变量报错条数 =", sum(1 for item in spec["errors"] if exprvm.locate(item["text"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
