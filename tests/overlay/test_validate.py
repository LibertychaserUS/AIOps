from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.overlay.support import copy_lg, run_overlay, write_generic_root


class ValidateTests(unittest.TestCase):
    def test_learning_guide_ok(self) -> None:
        from tests.overlay.support import LG

        result = run_overlay("validate", "--root", str(LG))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generic_adopter_ids_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_illegal_status_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_lg(Path(tmp))
            path = root / "suites" / "payment" / "suite.yaml"
            text = path.read_text(encoding="utf-8").replace("status: blocked", "status: pending")
            path.write_text(text, encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertTrue(
                "illegal status" in result.stderr or "not in" in result.stderr,
                result.stderr,
            )

    def test_blocked_without_reviewed_by_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_lg(Path(tmp))
            path = root / "suites" / "login" / "suite.yaml"
            text = path.read_text(encoding="utf-8").replace("reviewed_by: fixture", "reviewed_by: null")
            path.write_text(text, encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("reviewed_by", result.stderr)

    def test_does_not_require_product_id_regex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            cases = root / "suites" / "checkout-retry" / "cases.md"
            inbox = root / "inbox" / "checkout-retry.md"
            cases.write_text(
                cases.read_text(encoding="utf-8").replace("FN-login-retry", "hello.world"),
                encoding="utf-8",
            )
            inbox.write_text(
                inbox.read_text(encoding="utf-8").replace("FN-login-retry", "hello.world"),
                encoding="utf-8",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_inbox_forbidden_status_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            inbox = root / "inbox" / "checkout-retry.md"
            text = inbox.read_text(encoding="utf-8").replace("kind: user-case", "kind: user-case\nstatus: draft")
            inbox.write_text(text, encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 2)
            self.assertTrue("status" in result.stderr, result.stderr)


class KernelHygieneTests(unittest.TestCase):
    def test_overlay_has_no_product_imports(self) -> None:
        overlay = Path(__file__).resolve().parents[2] / "overlay"
        banned = ("LearningGuide", "ilovelearningguide", "ML-FR-", "LOGIN-01", "REQ-[")
        for path in overlay.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in banned:
                self.assertNotIn(token, text, f"{path.name} contains {token!r}")


if __name__ == "__main__":
    unittest.main()
