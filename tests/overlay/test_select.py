from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from overlay.select import Selection, SuiteDoc, assert_selection
from tests.overlay.support import GENERIC_SUITE, LG, copy_lg, run_overlay, write_generic_root


class SelectTests(unittest.TestCase):
    def test_main_selects_only_my_learning(self) -> None:
        result = run_overlay("select", "--branch", "main", "--root", str(LG))
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(selected, ["my-learning"])
        self.assertNotIn("payment", result.stdout)
        self.assertNotIn("login", result.stdout)
        self.assertIn("never_red_statuses", result.stderr + result.stdout)
        self.assertIn("dropped=2", result.stderr)

    def test_unknown_branch_is_empty_and_green(self) -> None:
        result = run_overlay("select", "--branch", "does-not-exist", "--root", str(LG))
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(selected, [])

    def test_hotfix_still_selects_functional_armed(self) -> None:
        result = run_overlay("select", "--branch", "hotfix", "--root", str(LG))
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(selected, ["my-learning"])

    def test_agent_subject_is_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            suite = root / "suites" / "checkout-retry" / "suite.yaml"
            suite.write_text(
                GENERIC_SUITE.replace("subject: product", "subject: agent"),
                encoding="utf-8",
            )
            result = run_overlay("select", "--branch", "main", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)
            selected = [line for line in result.stdout.splitlines() if line.strip()]
            self.assertEqual(selected, [])
            self.assertIn("kind_later", result.stderr)

    def test_illegal_status_select_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_lg(Path(tmp))
            path = root / "suites" / "my-learning" / "suite.yaml"
            path.write_text(
                path.read_text(encoding="utf-8").replace("status: armed", "status: ready"),
                encoding="utf-8",
            )
            result = run_overlay("select", "--branch", "main", "--root", str(root))
            self.assertEqual(result.returncode, 2)

    def test_assert_selected_blocked_is_exit_4(self) -> None:
        fake = SuiteDoc(
            path=Path("suites/x/suite.yaml"),
            suite_id="x",
            title="x",
            status="blocked",
            kind="functional",
            subject="product",
            source="inbox/x.md",
            reviewed_by="a",
            reviewed_at="2026-09-10T00:00:00Z",
            blocked_reason="no",
            armed_reason=None,
            cases_path=Path("suites/x/cases.md"),
            cases_text="# x\n",
            function_ids=[],
        )
        errors = assert_selection(Selection(selected=[fake], dropped=[]))
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
