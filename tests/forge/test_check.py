"""Local forge check: temp fixtures + this workshop. No GitHub write."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from forge import EXIT_OK
from forge.__main__ import main
from forge.check import EXIT_CHECK, run_check
from forge.title import EXAMPLE

ROOT = Path(__file__).resolve().parents[2]


def _ok(_root: Path, _stdout, _stderr) -> int:
    return EXIT_OK


def _fail(_root: Path, _stdout, _stderr) -> int:
    return EXIT_CHECK


class WorkshopCheckTests(unittest.TestCase):
    def test_workshop_check_with_title_is_green(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_check(
            ROOT,
            title=EXAMPLE,
            stdout=stdout,
            stderr=stderr,
            environ={},
            run_unittests=False,
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        out = stdout.getvalue()
        self.assertIn("forge check: ok", out)
        self.assertIn("overlay validate", out)
        self.assertIn("overlay cover", out)
        self.assertIn("pr-title", out)
        self.assertIn("schema/check.py", out)
        self.assertIn("sop-lock", out)
        self.assertNotIn("FAIL", out)

    def test_cli_check(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["check", "--root", str(ROOT), "--title", EXAMPLE],
            stdout=stdout,
            stderr=stderr,
            environ={},
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertIn("forge check: ok", stdout.getvalue())


class TitleStepTests(unittest.TestCase):
    def test_bad_title_is_red(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_check(
            Path("."),
            title="not a title",
            stdout=stdout,
            stderr=stderr,
            environ={},
            run_unittests=False,
            overlay_validate=_ok,
            overlay_cover=_ok,
            schema_runner=_ok,
        )
        self.assertEqual(code, EXIT_CHECK)
        self.assertIn("pr-title", stdout.getvalue())
        self.assertIn("FAIL", stdout.getvalue())
        self.assertIn("red", stderr.getvalue())

    def test_missing_title_skips_pr_title(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_check(
            Path("."),
            title=None,
            stdout=stdout,
            stderr=stderr,
            environ={},
            run_unittests=False,
            overlay_validate=_ok,
            overlay_cover=_ok,
            schema_runner=_ok,
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertIn("skip", stdout.getvalue())
        self.assertIn("no --title", stdout.getvalue())


class SkipAndFailTests(unittest.TestCase):
    def test_adopter_root_skips_overlay_and_schema(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = run_check(
                root,
                title=EXAMPLE,
                stdout=stdout,
                stderr=stderr,
                environ={},
                run_unittests=True,
            )
            self.assertEqual(code, EXIT_OK, stderr.getvalue())
            out = stdout.getvalue()
            self.assertIn("no overlay.yaml", out)
            self.assertIn("no schema/", out)
            self.assertIn("no workshop tests/", out)
            self.assertIn("pr-title", out)
            self.assertIn("ok", out)

    def test_sop_lock_failure_is_red(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".husky").mkdir()
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = run_check(
                root,
                title=EXAMPLE,
                stdout=stdout,
                stderr=stderr,
                environ={},
                run_unittests=False,
            )
            self.assertEqual(code, EXIT_CHECK)
            self.assertIn("sop-lock", stdout.getvalue())
            self.assertIn("FAIL", stdout.getvalue())

    def test_overlay_validate_failure_is_red(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "overlay.yaml").write_text("schema: overlay-config/v1\n", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = run_check(
                root,
                title=EXAMPLE,
                stdout=stdout,
                stderr=stderr,
                environ={},
                run_unittests=False,
                overlay_validate=_fail,
                overlay_cover=_ok,
            )
            self.assertEqual(code, EXIT_CHECK)
            self.assertIn("overlay validate", stdout.getvalue())
            self.assertIn("FAIL", stdout.getvalue())

    def test_skills_require_local_check(self) -> None:
        for name in ("dev-pr", "use-forge"):
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("python -m forge check", text)
        manage = (ROOT / "skills" / "manage-repo" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("代推", manage)
        self.assertIn("合入", manage)

    def test_pre_submit_hook_calls_check(self) -> None:
        hook = ROOT / "forge" / "hooks" / "pre-submit"
        text = hook.read_text(encoding="utf-8")
        self.assertIn("python3 -m forge check", text)
        self.assertIn("opt-in", text.lower())
        self.assertNotIn("npx husky", text.lower())
        self.assertNotIn("husky install", text.lower())
        self.assertTrue(hook.stat().st_mode & 0o111)


if __name__ == "__main__":
    unittest.main()
