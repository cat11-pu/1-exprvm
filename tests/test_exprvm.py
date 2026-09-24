import unittest

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


if __name__ == "__main__":
    unittest.main()
