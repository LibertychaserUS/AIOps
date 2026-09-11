from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.overlay.support import copy_lg, run_overlay, write_generic_root


MIGRATE_HINT = "python -m overlay migrate --root ."


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

    def test_removed_fields_exit_2_with_migrate_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            text = path.read_text(encoding="utf-8")
            text += "reviewed_by: fixture\nreviewed_at: 2026-09-10T00:00:00Z\narmed_reason: ready\n"
            path.write_text(text, encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 2, result.stdout)
            combined = result.stderr
            self.assertTrue(
                "reviewed_by" in combined or "reviewed_at" in combined or "armed_reason" in combined,
                combined,
            )
            self.assertIn(MIGRATE_HINT, combined)

    def test_draft_status_exit_2_with_migrate_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            path.write_text(
                path.read_text(encoding="utf-8").replace("status: active", "status: draft"),
                encoding="utf-8",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("draft/armed", result.stderr)
            self.assertIn(MIGRATE_HINT, result.stderr)

    def test_armed_status_exit_2_with_migrate_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            path.write_text(
                path.read_text(encoding="utf-8").replace("status: active", "status: armed"),
                encoding="utf-8",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("draft/armed", result.stderr)
            self.assertIn(MIGRATE_HINT, result.stderr)

    def test_v1_schema_exit_2_with_migrate_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "schema: overlay-suite/v2", "schema: overlay-suite/v1"
                ),
                encoding="utf-8",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("overlay-suite/v1", result.stderr)
            self.assertIn(MIGRATE_HINT, result.stderr)

    def test_missing_status_defaults_to_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            lines = [
                line
                for line in path.read_text(encoding="utf-8").splitlines()
                if not line.startswith("status:")
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)
            selected = run_overlay("select", "--branch", "main", "--root", str(root))
            self.assertEqual(selected.returncode, 0, selected.stderr)
            self.assertIn("checkout-retry", selected.stdout)

    def test_blocked_without_reason_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            text = path.read_text(encoding="utf-8")
            text = text.replace("status: active", "status: blocked")
            text = text.replace("blocked_reason: null", "blocked_reason: null")
            path.write_text(text, encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("blocked_reason", result.stderr)

    def test_blocked_reason_requires_link_or_register_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            text = path.read_text(encoding="utf-8")
            text = text.replace("status: active", "status: blocked")
            text = text.replace("blocked_reason: null", "blocked_reason: not ready yet")
            path.write_text(text, encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("blocked_reason", result.stderr)

    def test_blocked_reason_http_link_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            text = path.read_text(encoding="utf-8")
            text = text.replace("status: active", "status: blocked")
            text = text.replace(
                "blocked_reason: null",
                "blocked_reason: parked; see https://example.invalid/adr/0002",
            )
            path.write_text(text, encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_blocked_reason_of_id_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            text = path.read_text(encoding="utf-8")
            text = text.replace("status: active", "status: blocked")
            text = text.replace("blocked_reason: null", "blocked_reason: parked pending OF-12")
            path.write_text(text, encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_blocked_reason_hash_id_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            text = path.read_text(encoding="utf-8")
            text = text.replace("status: active", "status: blocked")
            text = text.replace("blocked_reason: null", "blocked_reason: 'parked pending #123'")
            path.write_text(text, encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_never_red_statuses_rejects_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            overlay = root / "overlay.yaml"
            overlay.write_text(
                overlay.read_text(encoding="utf-8").replace(
                    "never_red_statuses:\n  - blocked\n",
                    "never_red_statuses:\n  - draft\n  - blocked\n",
                ),
                encoding="utf-8",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("never_red_statuses", result.stderr)

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
            text = inbox.read_text(encoding="utf-8").replace("kind: user-case", "kind: user-case\nstatus: active")
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
