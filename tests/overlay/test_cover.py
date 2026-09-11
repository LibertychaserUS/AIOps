from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from overlay import EXIT_CONTRACT, EXIT_OK
from tests.overlay.support import GENERIC_CASES, LG, REPO, copy_lg, run_overlay, write, write_generic_root


class CoverTests(unittest.TestCase):
    def test_help_lists_cover(self) -> None:
        result = run_overlay("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cover", result.stdout)

    def test_workshop_cover_ok(self) -> None:
        result = run_overlay("cover", "--root", str(REPO))
        self.assertEqual(result.returncode, EXIT_OK, result.stderr + result.stdout)
        self.assertIn("FN-overlay-select", result.stdout)
        self.assertIn("INV-never-red-blocked", result.stdout)
        self.assertIn("cited=yes", result.stdout)
        self.assertIn("functional=yes", result.stdout)

    def test_learning_guide_cover_ok_without_invariants_file(self) -> None:
        result = run_overlay("cover", "--root", str(LG))
        self.assertEqual(result.returncode, EXIT_OK, result.stderr + result.stdout)
        self.assertIn("no invariants.yaml", result.stdout)
        self.assertIn("ML-FR-004", result.stdout)
        self.assertNotIn("interaction hints", result.stdout)

    def test_active_missing_edge_is_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            cases = root / "suites" / "checkout-retry" / "cases.md"
            cases.write_text(
                GENERIC_CASES.replace("### Edge", "### Other"),
                encoding="utf-8",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)
            self.assertIn("missing techniques", result.stderr)
            self.assertIn("edge", result.stderr)

    def test_blocked_missing_edge_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            suite = root / "suites" / "checkout-retry" / "suite.yaml"
            data = yaml.safe_load(suite.read_text(encoding="utf-8"))
            data["status"] = "blocked"
            data["blocked_reason"] = "not ready; see https://example.invalid/of"
            suite.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            cases = root / "suites" / "checkout-retry" / "cases.md"
            cases.write_text(
                GENERIC_CASES.replace("### Edge", "### Other"),
                encoding="utf-8",
            )
            result = run_overlay("cover", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_OK, result.stderr + result.stdout)
            self.assertIn("hint: missing edge", result.stdout)

    def test_uncited_invariant_is_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            write(
                root / "invariants.yaml",
                """\
schema: overlay-invariants/v1
items:
  - id: INV-one-charge
    text: One receipt never creates two charges
    function_ids:
      - FN-login-retry
    span: system
""",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)
            self.assertIn("INV-one-charge", result.stderr)

    def test_active_siblings_without_interaction_print_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_lg(Path(tmp))
            cases = root / "suites" / "my-learning" / "cases.md"
            cases.write_text(
                cases.read_text(encoding="utf-8").replace("ML-FR-007", "unique-LP"),
                encoding="utf-8",
            )
            # Restore the heading id we just broke.
            cases.write_text(
                cases.read_text(encoding="utf-8").replace(
                    "## unique-LP Unique Learning Point progress",
                    "## ML-FR-007 Unique Learning Point progress",
                ),
                encoding="utf-8",
            )
            trace = root / "suites" / "my-learning" / "trace.yaml"
            data = yaml.safe_load(trace.read_text(encoding="utf-8"))
            data["items"] = [item for item in data["items"] if item.get("span") != "interaction"]
            trace.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            result = run_overlay("cover", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_OK, result.stderr + result.stdout)
            self.assertIn("interaction hints", result.stdout)

    def test_unknown_relates_is_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            write(
                root / "suites" / "checkout-retry" / "trace.yaml",
                """\
schema: overlay-trace/v1
suite: checkout-retry
items:
  - function_id: FN-login-retry
    case_id: FN-login-retry/functional
    type: functional
    relates:
      - FN-does-not-exist
""",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)
            self.assertIn("FN-does-not-exist", result.stderr)


if __name__ == "__main__":
    unittest.main()
