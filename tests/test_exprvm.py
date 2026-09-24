import unittest

import exprvm
import rules
from exprvm import ExprError, evaluate


class TestExpr(unittest.TestCase):
    def test_sum_pieces(self):
        self.assertEqual(evaluate("1 2 3"), 6)

    def test_bad_piece(self):
        with self.assertRaises(ExprError):
            evaluate("1 x")

    def test_engine_uses_legacy(self):
        engine = rules.RuleEngine()
        self.assertEqual(engine.check("2 3"), 5)

    def test_scope_set(self):
        engine = rules.RuleEngine()
        engine.set("a", 3)
        self.assertEqual(engine.scope["a"], 3)

    def test_engine_scope_default(self):
        self.assertEqual(rules.RuleEngine().scope, {})


class TestCompileRun(unittest.TestCase):
    def test_precedence(self):
        code = exprvm.compile_expression("a + 3 * 4")
        self.assertEqual(len(code), 5)
        self.assertEqual(exprvm.run(code, {"a": 2}), 14)

    def test_parens(self):
        code = exprvm.compile_expression("(a + 3) * 4")
        self.assertEqual(len(code), 7)
        self.assertEqual(exprvm.run(code, {"a": 2}), 20)

    def test_unary_signs(self):
        code = exprvm.compile_expression("-a + +c")
        self.assertEqual(len(code), 5)
        self.assertEqual(exprvm.run(code, {"a": 2, "c": 5}), 3)

    def test_short_circuit_and(self):
        code = exprvm.compile_expression("b != 0 and c / b")
        self.assertEqual(len(code), 10)
        self.assertEqual(exprvm.run(code, {"b": 0, "c": 5}), 0)
        self.assertEqual(exprvm.short_circuit_count(code), 4)

    def test_short_circuit_or(self):
        code = exprvm.compile_expression("a > 1 or c < 1")
        self.assertEqual(len(code), 8)
        self.assertEqual(exprvm.run(code, {"a": 2, "c": 5}), 1)
        self.assertEqual(exprvm.short_circuit_count(code), 4)

    def test_short_circuit_count_fresh_code(self):
        code = exprvm.compile_expression("b != 0 and c / b")
        self.assertEqual(exprvm.short_circuit_count(code), 0)

    def test_div_zero(self):
        with self.assertRaises(ExprError):
            exprvm.run(exprvm.compile_expression("1 / 0"), {})

    def test_undefined_variable(self):
        with self.assertRaises(ExprError):
            exprvm.run(exprvm.compile_expression("x + 1"), {})

    def test_locate(self):
        self.assertEqual(exprvm.locate("a + "), 4)
        self.assertEqual(exprvm.locate("(a + 3"), 6)
        self.assertEqual(exprvm.locate("a @ 3"), 5)
        self.assertEqual(exprvm.locate("a + 1"), 0)

    def test_check_all(self):
        engine = rules.RuleEngine()
        engine.set("a", 2)
        self.assertEqual(engine.check_all(["a + 3 * 4", "(a + 3) * 4"]), [14, 20])


if __name__ == "__main__":
    unittest.main()
