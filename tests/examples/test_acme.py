"""Acme Python adopter example: overlay validate/cover + forge check.

forge check runs on a fresh git clone of the example (a real adopter's clean
checkout), so the workshop branch's own diff never leaks into deny_paths.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACME = ROOT / "examples" / "acme-python"


def _run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


class AcmeInventoryTests(unittest.TestCase):
    def test_product_command_unittest_is_green(self) -> None:
        result = _run(["-m", "unittest", "discover", "-s", "tests", "-q"], cwd=ACME)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


def _git(cwd: Path, *args: str) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "-C", str(cwd), "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, env=env)


def _adopter_clone() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="acme-adopter-"))
    dest = tmp / "inventory-api"
    shutil.copytree(ACME, dest)
    _git(dest, "init", "-b", "main")
    _git(dest, "config", "user.email", "t@example.test")
    _git(dest, "config", "user.name", "T")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-m", "adopt overlay and forge")
    return dest


class AcmeOverlayForgeTests(unittest.TestCase):
    def test_overlay_validate_green(self) -> None:
        result = _run(["-m", "overlay", "validate", "--root", str(ACME)], cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_overlay_cover_green(self) -> None:
        result = _run(["-m", "overlay", "cover", "--root", str(ACME)], cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_forge_check_green_on_a_clean_adopter_clone(self) -> None:
        clone = _adopter_clone()
        try:
            result = _run(["-m", "forge", "check", "--root", str(clone)], cwd=clone)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertNotIn("sop-lock", result.stdout, "workshop-only rows must not print for an adopter")
            self.assertIn("deny_paths", result.stdout)
            self.assertIn("suite_guard", result.stdout)
            self.assertIn("docs_sync", result.stdout)
        finally:
            shutil.rmtree(clone.parent, ignore_errors=True)

    def test_agent_branch_touching_the_workflow_is_red_for_the_adopter(self) -> None:
        clone = _adopter_clone()
        try:
            _git(clone, "checkout", "-b", "agent/ci-tweak")
            wf = clone / ".github" / "workflows" / "overlay-check.yml"
            wf.write_text(wf.read_text(encoding="utf-8") + "# tweak\n", encoding="utf-8")
            result = _run(["-m", "forge", "check", "--root", str(clone)], cwd=clone)
            self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
            self.assertIn("deny_paths", result.stdout)
            self.assertIn("FAIL", result.stdout)
        finally:
            shutil.rmtree(clone.parent, ignore_errors=True)
