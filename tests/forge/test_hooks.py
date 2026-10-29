"""forge/hooks/* are thin sh wrappers over python -m forge. Run them for real."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from forge.check import EXIT_CHECK
from forge.title import EXAMPLE, EXIT_TITLE

from forge import EXIT_OK

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "forge" / "hooks"


def _run(hook: str, *args: str, cwd: Path, extra_env: dict[str, str] | None = None):
    # The hooks exec `python3 -m forge`: resolve python3 to this interpreter
    # and make the workshop importable from any cwd.
    env = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "PYTHONPATH": str(ROOT),
    }
    env.pop("PR_TITLE", None)
    env.pop("GITHUB_EVENT_NAME", None)
    env.update(extra_env or {})
    return subprocess.run(
        ["sh", str(HOOKS / hook), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )


class PrTitleHookTests(unittest.TestCase):
    def test_good_title_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run("pr-title", EXAMPLE, cwd=Path(tmp))
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)

    def test_bad_title_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run("pr-title", "[开发][Overlay] add cover", cwd=Path(tmp))
        self.assertEqual(proc.returncode, EXIT_TITLE)
        self.assertIn("Conventional Commits", proc.stderr)

    def test_env_title_is_used_when_no_arg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            good = _run("pr-title", cwd=Path(tmp), extra_env={"PR_TITLE": EXAMPLE})
            bad = _run("pr-title", cwd=Path(tmp), extra_env={"PR_TITLE": "feat(overlay): no actor"})
        self.assertEqual(good.returncode, EXIT_OK, good.stderr)
        self.assertEqual(bad.returncode, EXIT_TITLE)

    def test_help_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run("pr-title", "--help", cwd=Path(tmp))
        self.assertEqual(proc.returncode, EXIT_OK)
        self.assertIn("usage", proc.stderr)


class PreSubmitHookTests(unittest.TestCase):
    def test_not_a_product_root_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run("pre-submit", "--title", EXAMPLE, cwd=Path(tmp))
        self.assertEqual(proc.returncode, EXIT_CHECK)
        self.assertIn("not a product root", proc.stderr)

    def test_root_flag_is_passed_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            proc = _run("pre-submit", "--root", str(empty), cwd=Path(tmp))
        self.assertEqual(proc.returncode, EXIT_CHECK)
        self.assertIn("not a product root", proc.stderr)

    def test_bad_title_on_minimal_root_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text("schema: forge-config/v1\nprotect:\n  - main\n", encoding="utf-8")
            proc = _run("pre-submit", "--title", "not a title", cwd=root)
        self.assertEqual(proc.returncode, EXIT_CHECK)
        self.assertIn("pr-title", proc.stdout + proc.stderr)

    def test_help_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run("pre-submit", "-h", cwd=Path(tmp))
        self.assertEqual(proc.returncode, EXIT_OK)
        self.assertIn("opt-in only", proc.stderr)


if __name__ == "__main__":
    unittest.main()
