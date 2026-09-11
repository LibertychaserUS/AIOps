from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from overlay.select import Selection, SuiteDoc, assert_selection
from tests.overlay.support import GENERIC_SUITE, LG, REPO, copy_lg, run_overlay, write_generic_root


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
        self.assertTrue(
            "blocked_reason" in result.stderr or "reason=" in result.stderr,
            result.stderr,
        )

    def test_unknown_branch_falls_back_to_main(self) -> None:
        result = run_overlay("select", "--branch", "does-not-exist", "--root", str(LG))
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(selected, ["my-learning"])
        self.assertTrue(
            "does-not-exist" in result.stderr and "main" in result.stderr,
            result.stderr,
        )

    def test_unknown_branch_falls_back_to_branches_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            overlay = root / "overlay.yaml"
            overlay.write_text(
                overlay.read_text(encoding="utf-8").replace(
                    "  default:\n    run: [functional]\n",
                    "  default:\n    run: [regression]\n",
                ),
                encoding="utf-8",
            )
            result = run_overlay("select", "--branch", "no-such-branch", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)
            selected = [line for line in result.stdout.splitlines() if line.strip()]
            self.assertEqual(selected, [])
            self.assertIn("default", result.stderr)
            self.assertIn("no-such-branch", result.stderr)

    def test_hotfix_still_selects_functional_active(self) -> None:
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
                path.read_text(encoding="utf-8").replace("status: active", "status: ready"),
                encoding="utf-8",
            )
            result = run_overlay("select", "--branch", "main", "--root", str(root))
            self.assertEqual(result.returncode, 2)

    def test_workshop_main_does_not_select_forge_apply(self) -> None:
        result = run_overlay("select", "--branch", "main", "--root", str(REPO))
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(selected, ["overlay-select"])
        self.assertNotIn("forge-apply", selected)

    def test_assert_selected_blocked_is_exit_4(self) -> None:
        fake = SuiteDoc(
            path=Path("suites/x/suite.yaml"),
            suite_id="x",
            title="x",
            status="blocked",
            kind="functional",
            subject="product",
            source="inbox/x.md",
            blocked_reason="no; see OF-12",
            cases_path=Path("suites/x/cases.md"),
            cases_text="# x\n",
            function_ids=[],
        )
        errors = assert_selection(Selection(selected=[fake], dropped=[]))
        self.assertTrue(errors)

    def test_branch_defaults_to_github_base_ref(self) -> None:
        result = run_overlay(
            "select",
            "--root",
            str(LG),
            env={"GITHUB_BASE_REF": "hotfix", "GITHUB_REF_NAME": "cursor/ignored"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(selected, ["my-learning"])

    def test_branch_defaults_to_github_ref_name(self) -> None:
        result = run_overlay(
            "select",
            "--root",
            str(LG),
            env={"GITHUB_BASE_REF": "", "GITHUB_REF_NAME": "hotfix"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(selected, ["my-learning"])

    def test_branch_defaults_to_main(self) -> None:
        result = run_overlay(
            "select",
            "--root",
            str(LG),
            env={"GITHUB_BASE_REF": "", "GITHUB_REF_NAME": ""},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(selected, ["my-learning"])


if __name__ == "__main__":
    unittest.main()
