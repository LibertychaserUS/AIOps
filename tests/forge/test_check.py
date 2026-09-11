"""Local forge check: temp fixtures + this workshop. No GitHub write."""

from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from forge import EXIT_OK
from forge.__main__ import main
from forge.check import EXIT_CHECK, deny_paths_step, path_is_denied, run_check
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
            ROOT,
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
        self.assertIn("CI lints PR_TITLE", stdout.getvalue())
        self.assertIn("pr-body", stdout.getvalue())
        self.assertIn("CI lints PR_BODY", stdout.getvalue())

    def test_bad_body_is_red_when_brief_exists(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_check(
            ROOT,
            title=EXAMPLE,
            body="## 做了什么\n",
            stdout=stdout,
            stderr=stderr,
            environ={},
            run_unittests=False,
        )
        self.assertEqual(code, EXIT_CHECK)
        self.assertIn("pr-body", stdout.getvalue())
        self.assertIn("FAIL", stdout.getvalue())

    def test_good_body_is_green_when_brief_exists(self) -> None:
        from forge.brief import REQUIRED_H2

        body = "\n\n".join(f"## {heading}\n\n-" for heading in REQUIRED_H2)
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_check(
            ROOT,
            title=EXAMPLE,
            body=body,
            stdout=stdout,
            stderr=stderr,
            environ={},
            run_unittests=False,
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertIn("pr-body", stdout.getvalue())
        self.assertNotIn("FAIL", stdout.getvalue())


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


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _init_product(root: Path) -> None:
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    (root / "forge.yaml").write_text(
        "schema: forge-config/v1\n"
        "protect:\n"
        "  - main\n"
        "agent_branch_prefixes:\n"
        "  - cursor/\n"
        "  - copilot/\n"
        "deny_paths:\n"
        "  - .github/workflows/ci.yml\n",
        encoding="utf-8",
    )
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.test")
    _git(root, "config", "user.name", "T")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


class DenyPathsCheckTests(unittest.TestCase):
    def test_readme_only_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product(root)
            _git(root, "checkout", "-b", "cursor/docs")
            (root / "README.md").write_text("hello world\n", encoding="utf-8")
            _git(root, "add", "README.md")
            _git(root, "commit", "-m", "docs")
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
            self.assertEqual(code, EXIT_OK, stderr.getvalue())
            out = stdout.getvalue()
            self.assertIn("deny_paths", out)
            self.assertNotIn("FAIL", out)
            self.assertIn("agent branch cursor/docs", out)

    def test_deny_path_commit_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product(root)
            _git(root, "checkout", "-b", "cursor/ci")
            (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\non: push\n", encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "touch deny")
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
            out = stdout.getvalue()
            self.assertIn("deny_paths", out)
            self.assertIn("FAIL", out)
            self.assertIn(".github/workflows/ci.yml", out)
            self.assertIn("agent branch cursor/ci", out)

    def test_human_branch_also_fails_on_deny_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product(root)
            _git(root, "checkout", "-b", "feature/ci")
            (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\non: push\n", encoding="utf-8")
            stdout = io.StringIO()
            code = run_check(
                root,
                title=EXAMPLE,
                stdout=stdout,
                stderr=io.StringIO(),
                environ={},
                run_unittests=False,
            )
            self.assertEqual(code, EXIT_CHECK)
            self.assertIn(".github/workflows/ci.yml", stdout.getvalue())
            self.assertNotIn("agent branch", stdout.getvalue())

    def test_no_forge_yaml_skips_deny_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            step = deny_paths_step(root)
            self.assertEqual(step.status, "skip")
            self.assertIn("no forge.yaml", step.detail)

    def test_path_match_is_exact_or_directory(self) -> None:
        deny = [".github/workflows/ci.yml", "docs/locked"]
        self.assertTrue(path_is_denied(".github/workflows/ci.yml", deny))
        self.assertTrue(path_is_denied("./.github/workflows/ci.yml", deny))
        self.assertFalse(path_is_denied(".github/workflows/ci.yml.bak", deny))
        self.assertTrue(path_is_denied("docs/locked/readme.md", deny))
        self.assertFalse(path_is_denied("docs/open.md", deny))
        self.assertFalse(path_is_denied("github/workflows/ci.yml", deny))


if __name__ == "__main__":
    unittest.main()
