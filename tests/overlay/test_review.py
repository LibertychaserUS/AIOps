"""overlay review writes only on a human branch with --i-am."""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from overlay.review import run_review

from overlay import EXIT_CONTRACT, EXIT_OK
from tests.overlay.support import write_generic_root

FORGE = """\
schema: forge-config/v1
protect:
  - dev
agent_branch_prefixes:
  - cursor/
  - copilot/
  - agent/
"""


def _git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        env=env,
    )


def _init(root: Path, branch: str) -> None:
    (root / "forge.yaml").write_text(FORGE, encoding="utf-8")
    _git(root, "init", "-b", branch)
    _git(root, "config", "user.email", "t@example.test")
    _git(root, "config", "user.name", "T")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


class ReviewTests(unittest.TestCase):
    def test_refuses_without_i_am(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            code = run_review(root=root, i_am=None, suite="checkout-retry", status="active", reason="x")
            self.assertEqual(code, EXIT_CONTRACT)

    def test_refuses_without_forge_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            code = run_review(
                root=root,
                i_am="ada",
                suite="checkout-retry",
                status="active",
                reason="signed",
            )
            self.assertEqual(code, EXIT_CONTRACT)

    def test_agent_branch_cannot_set_or_clear_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            original = path.read_text(encoding="utf-8").replace("status: active", "status: blocked")
            original = original.replace("blocked_reason: null", "blocked_reason: parked #12")
            path.write_text(original, encoding="utf-8")
            _init(root, "cursor/agent-slice")
            err = io.StringIO()
            code = run_review(
                root=root,
                i_am="ada",
                suite="checkout-retry",
                status="active",
                reason="https://example.com/clear",
                stderr=err,
            )
            self.assertEqual(code, EXIT_CONTRACT)
            self.assertIn("agent branch", err.getvalue())
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            code_block = run_review(
                root=root,
                i_am="ada",
                suite="checkout-retry",
                status="blocked",
                reason="see #99",
            )
            self.assertEqual(code_block, EXIT_CONTRACT)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_human_can_set_blocked_and_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            _init(root, "dev")
            code = run_review(
                root=root,
                i_am="ada",
                suite="checkout-retry",
                status="blocked",
                reason="parked pending #12",
            )
            self.assertEqual(code, EXIT_OK)
            blocked = path.read_text(encoding="utf-8")
            self.assertIn("status: blocked", blocked)
            self.assertIn("#12", blocked)
            self.assertNotIn("reviewed_by", blocked)
            self.assertIn("product_command:", blocked)
            bare = run_review(
                root=root,
                i_am="ada",
                suite="checkout-retry",
                status="blocked",
                reason="not ready yet",
            )
            self.assertEqual(bare, EXIT_CONTRACT)
            self.assertIn("status: blocked", path.read_text(encoding="utf-8"))
            opened = run_review(
                root=root,
                i_am="ada",
                suite="checkout-retry",
                status="active",
                reason="human signed",
            )
            self.assertEqual(opened, EXIT_OK)
            active = path.read_text(encoding="utf-8")
            self.assertIn("status: active", active)
            self.assertIn("blocked_reason: null", active)
            self.assertNotIn("reviewed_by", active)

    def test_active_requires_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            _init(root, "dev")
            code = run_review(
                root=root,
                i_am="ada",
                suite="checkout-retry",
                status="active",
                reason="  ",
            )
            self.assertEqual(code, EXIT_CONTRACT)


if __name__ == "__main__":
    unittest.main()
