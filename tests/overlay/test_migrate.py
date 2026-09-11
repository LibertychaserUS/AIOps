from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.overlay.support import run_overlay, write, write_generic_root


ARMED_V1 = """\
# keep-me: packages stay below
id: checkout-retry
title: Checkout retry without double charge
status: armed
kind: functional
subject: product
source: inbox/checkout-retry.md
packages:
  - src/checkout
reviewed_by: fixture
reviewed_at: 2026-09-10T00:00:00Z
blocked_reason: null
armed_reason: Pin already ships the retry path.
product_command: null
"""

BLOCKED_WITH_REASON_V1 = """\
id: parked
title: Parked slice
status: blocked
kind: functional
subject: product
source: inbox/parked.md
reviewed_by: fixture
reviewed_at: 2026-09-10T00:00:00Z
blocked_reason: not ready; tracked as OF-12
armed_reason: null
product_command: null
"""

BLOCKED_NO_REASON_V1 = """\
id: parked
title: Parked slice
status: blocked
kind: functional
subject: product
source: inbox/parked.md
reviewed_by: fixture
reviewed_at: 2026-09-10T00:00:00Z
blocked_reason: null
armed_reason: null
product_command: null
"""


class MigrateTests(unittest.TestCase):
    def test_help_lists_migrate(self) -> None:
        result = run_overlay("migrate", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--root", result.stdout)
        self.assertIn("--dry-run", result.stdout)

    def test_armed_rewritten_to_active_line_preserving(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            path.write_text(ARMED_V1, encoding="utf-8")
            overlay = root / "overlay.yaml"
            overlay.write_text(
                overlay.read_text(encoding="utf-8").replace(
                    "never_red_statuses:\n  - blocked\n",
                    "never_red_statuses:\n  - draft\n  - blocked\n",
                ),
                encoding="utf-8",
            )
            result = run_overlay("migrate", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            text = path.read_text(encoding="utf-8")
            self.assertIn("schema: overlay-suite/v2", text)
            self.assertIn("status: active", text)
            self.assertNotIn("status: armed", text)
            self.assertNotIn("reviewed_by", text)
            self.assertNotIn("reviewed_at", text)
            self.assertNotIn("armed_reason", text)
            self.assertIn("# keep-me: packages stay below", text)
            self.assertLess(text.index("# keep-me"), text.index("packages:"))
            self.assertIn("  - src/checkout", text)
            overlay_text = overlay.read_text(encoding="utf-8")
            self.assertNotIn("- draft", overlay_text)
            self.assertIn("- blocked", overlay_text)

    def test_blocked_with_reason_keeps_status_strips_old_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            write(root / "overlay.yaml", "schema: overlay-config/v1\nnever_red_statuses:\n  - blocked\n")
            write(root / "suites" / "parked" / "suite.yaml", BLOCKED_WITH_REASON_V1)
            result = run_overlay("migrate", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            text = (root / "suites" / "parked" / "suite.yaml").read_text(encoding="utf-8")
            self.assertIn("status: blocked", text)
            self.assertIn("blocked_reason: not ready; tracked as OF-12", text)
            self.assertNotIn("reviewed_by", text)
            self.assertNotIn("armed_reason", text)
            self.assertIn("schema: overlay-suite/v2", text)

    def test_blocked_without_reason_is_unchanged_and_prints_todo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            write(root / "suites" / "parked" / "suite.yaml", BLOCKED_NO_REASON_V1)
            result = run_overlay("migrate", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            text = (root / "suites" / "parked" / "suite.yaml").read_text(encoding="utf-8")
            self.assertEqual(text, BLOCKED_NO_REASON_V1)
            combined = result.stderr + result.stdout
            self.assertTrue("parked" in combined, combined)
            self.assertTrue(
                "todo" in combined.lower() or "待办" in combined or "blocked_reason" in combined,
                combined,
            )

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            path.write_text(ARMED_V1, encoding="utf-8")
            result = run_overlay("migrate", "--root", str(root), "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(path.read_text(encoding="utf-8"), ARMED_V1)
            self.assertTrue(
                "checkout-retry" in result.stdout + result.stderr
                or "active" in result.stdout + result.stderr,
                result.stdout + result.stderr,
            )


if __name__ == "__main__":
    unittest.main()
