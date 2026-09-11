from __future__ import annotations

import unittest

from tests.overlay.support import LG, run_overlay


class CliTests(unittest.TestCase):
    def test_module_help(self) -> None:
        result = run_overlay("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validate", result.stdout)
        self.assertIn("select", result.stdout)
        self.assertIn("run", result.stdout)
        self.assertIn("cover", result.stdout)
        self.assertIn("migrate", result.stdout)

    def test_validate_help(self) -> None:
        result = run_overlay("validate", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--root", result.stdout)

    def test_select_help(self) -> None:
        result = run_overlay("select", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--branch", result.stdout)
        self.assertIn("--write-receipt", result.stdout)

    def test_generate_is_not_implemented(self) -> None:
        result = run_overlay("generate")
        self.assertNotEqual(result.returncode, 0)

    def test_review_refuses_without_i_am(self) -> None:
        result = run_overlay("review", "--suite", "my-learning", "--status", "active")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--i-am", result.stderr)

    def test_validate_learning_guide_fixture(self) -> None:
        result = run_overlay("validate", "--root", str(LG))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
