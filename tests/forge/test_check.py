"""Local forge check: temp fixtures + this workshop. No GitHub write."""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from forge import EXIT_OK
from forge.__main__ import main
from forge.check import EXIT_CHECK, deny_paths_step, path_is_denied, run_check, suite_guard_step
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
    def test_adopter_root_omits_workshop_only_rows(self) -> None:
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
            self.assertIn("pr-title", out)
            self.assertNotIn("schema/check.py", out)
            self.assertNotIn("sop-lock", out)
            self.assertNotIn("unittest (fast)", out)
            self.assertNotIn("no workshop tests/", out)
            self.assertIn("ok", out)

    def test_adopter_husky_does_not_print_sop_lock(self) -> None:
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
            self.assertEqual(code, EXIT_OK, stderr.getvalue())
            self.assertNotIn("sop-lock", stdout.getvalue())

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
    # Isolate from the developer's global git config: a commit signer
    # (commit.gpgsign + gpg.ssh.program) turns each fixture commit into a
    # multi-second RPC and can prompt. Fixtures never need signatures.
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        env=env,
    )


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


ACTIVE_SUITE = (
    "id: login\n"
    "status: active\n"
    "product_command: true\n"
)
BLOCKED_SUITE = (
    "id: login\n"
    "status: blocked\n"
    "blocked_reason: parked pending https://example.test/OF-12\n"
    "product_command: true\n"
)


def _init_product_with_suite(root: Path) -> None:
    _init_product(root)
    (root / "suites" / "login").mkdir(parents=True)
    (root / "suites" / "login" / "suite.yaml").write_text(ACTIVE_SUITE, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "draft suite")


def _check(root: Path, environ: dict[str, str] | None = None) -> tuple[int, str]:
    stdout = io.StringIO()
    code = run_check(
        root,
        title=EXAMPLE,
        stdout=stdout,
        stderr=io.StringIO(),
        environ=environ or {},
        run_unittests=False,
    )
    return code, stdout.getvalue()


class ProtectBaseResolutionTests(unittest.TestCase):
    def test_stale_local_main_does_not_produce_false_hits(self) -> None:
        # A developer whose local main is behind origin/main must not see the
        # merged work of others reported as their own deny_paths / arm diff.
        with tempfile.TemporaryDirectory() as tmp:
            remote = Path(tmp) / "remote.git"
            remote.mkdir()
            _git(remote, "init", "--bare", "-b", "main")
            root = Path(tmp) / "clone"
            root.mkdir()
            _init_product_with_suite(root)
            _git(root, "remote", "add", "origin", str(remote))
            _git(root, "push", "-q", "origin", "main")
            # Someone else lands a deny_path change and arms the suite on origin/main.
            other = Path(tmp) / "other"
            _git(Path(tmp), "clone", "-q", str(remote), str(other))
            _git(other, "config", "user.email", "o@example.test")
            _git(other, "config", "user.name", "O")
            (other / ".github" / "workflows" / "ci.yml").write_text("name: ci\non: push\n", encoding="utf-8")
            (other / "suites" / "login" / "suite.yaml").write_text(BLOCKED_SUITE, encoding="utf-8")
            _git(other, "add", "-A")
            _git(other, "commit", "-m", "human lands ci + arms")
            _git(other, "push", "-q", "origin", "main")
            # Our clone: local main stale, fetch origin, branch from origin/main, touch README only.
            _git(root, "fetch", "-q", "origin")
            _git(root, "checkout", "-q", "-b", "cursor/docs", "origin/main")
            (root / "README.md").write_text("hello again\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_OK, out)
            self.assertIn("vs refs/remotes/origin/main", out)


class MonorepoRootTests(unittest.TestCase):
    """--root may be a subdirectory of the git repo (monorepo adopter)."""

    def _init_monorepo(self, top: Path) -> Path:
        (top / ".github" / "workflows").mkdir(parents=True)
        (top / ".github" / "workflows" / "ci.yml").write_text("name: top\n", encoding="utf-8")
        product = top / "services" / "inventory"
        product.mkdir(parents=True)
        (product / ".github" / "workflows").mkdir(parents=True)
        (product / ".github" / "workflows" / "ci.yml").write_text("name: product\n", encoding="utf-8")
        (product / "README.md").write_text("hello\n", encoding="utf-8")
        (product / "forge.yaml").write_text(
            "schema: forge-config/v1\nprotect:\n  - main\nagent_branch_prefixes:\n  - cursor/\n"
            "deny_paths:\n  - .github/workflows/\n",
            encoding="utf-8",
        )
        _git(top, "init", "-b", "main")
        _git(top, "config", "user.email", "t@example.test")
        _git(top, "config", "user.name", "T")
        _git(top, "add", "-A")
        _git(top, "commit", "-m", "init")
        return product

    def test_top_level_workflow_change_is_not_the_products_deny_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp)
            product = self._init_monorepo(top)
            _git(top, "checkout", "-b", "cursor/top")
            (top / ".github" / "workflows" / "ci.yml").write_text("name: top2\n", encoding="utf-8")
            code, out = _check(product)
            self.assertEqual(code, EXIT_OK, out)

    def test_product_workflow_change_is_red_with_product_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp)
            product = self._init_monorepo(top)
            _git(top, "checkout", "-b", "cursor/prod")
            (product / ".github" / "workflows" / "ci.yml").write_text("name: product2\n", encoding="utf-8")
            code, out = _check(product)
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("diff touches .github/workflows/ci.yml", out)
            self.assertNotIn("services/inventory/.github", out)


class SuiteGuardCheckTests(unittest.TestCase):
    """Agents must not flip status to blocked; humans are recorded."""

    def test_agent_branch_blocking_a_suite_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product_with_suite(root)
            _git(root, "checkout", "-b", "cursor/block")
            (root / "suites" / "login" / "suite.yaml").write_text(BLOCKED_SUITE, encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "block")
            code, out = _check(root)
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("suite_guard", out)
            self.assertIn("FAIL", out)
            self.assertIn("suites/login/suite.yaml", out)
            self.assertIn("blocked", out)
            self.assertNotIn("armed", out)
            self.assertNotIn("reviewed_by", out)

    def test_agent_branch_new_active_suite_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product_with_suite(root)
            _git(root, "checkout", "-b", "cursor/new-suite")
            (root / "suites" / "payment").mkdir()
            (root / "suites" / "payment" / "suite.yaml").write_text(
                ACTIVE_SUITE.replace("id: login", "id: payment"), encoding="utf-8"
            )
            code, out = _check(root)
            self.assertEqual(code, EXIT_OK, out)
            self.assertIn("suite_guard", out)
            self.assertNotIn("FAIL", out)

    def test_human_branch_blocking_is_recorded_not_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product_with_suite(root)
            _git(root, "checkout", "-b", "review/block-login")
            (root / "suites" / "login" / "suite.yaml").write_text(BLOCKED_SUITE, encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_OK, out)
            self.assertIn("suite_guard", out)
            self.assertIn("human branch", out)

    def test_detached_head_uses_github_head_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product_with_suite(root)
            _git(root, "checkout", "-b", "cursor/block")
            (root / "suites" / "login" / "suite.yaml").write_text(BLOCKED_SUITE, encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "block")
            _git(root, "checkout", "--detach")
            code, out = _check(root, {"GITHUB_HEAD_REF": "cursor/block"})
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("agent branch cursor/block", out)

    def test_already_blocked_on_main_stays_green_for_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product_with_suite(root)
            (root / "suites" / "login" / "suite.yaml").write_text(BLOCKED_SUITE, encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "human blocks on main")
            _git(root, "checkout", "-b", "cursor/touch")
            (root / "suites" / "login" / "suite.yaml").write_text(
                BLOCKED_SUITE.replace("OF-12", "OF-12#note"), encoding="utf-8"
            )
            code, out = _check(root)
            self.assertEqual(code, EXIT_OK, out)

    def test_no_suites_dir_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product(root)
            _git(root, "checkout", "-b", "cursor/none")
            step = suite_guard_step(root, environ={})
            self.assertEqual(step.status, "ok")
            self.assertIn("no suite.yaml", step.detail)


class DocsSyncCheckTests(unittest.TestCase):
    def test_table_miss_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product(root)
            (root / "forge.yaml").write_text(
                "schema: forge-config/v1\n"
                "protect:\n  - main\n"
                "agent_branch_prefixes:\n  - cursor/\n"
                "deny_paths:\n  - .github/workflows/ci.yml\n"
                "docs_sync:\n"
                "  - paths: [src/**]\n"
                "    require: [CHANGELOG.md]\n",
                encoding="utf-8",
            )
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "config")
            _git(root, "checkout", "-b", "cursor/src")
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("docs_sync", out)
            self.assertIn("FAIL", out)
            self.assertIn("CHANGELOG.md", out)

    def test_table_hit_with_require_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product(root)
            (root / "forge.yaml").write_text(
                "schema: forge-config/v1\n"
                "protect:\n  - main\n"
                "agent_branch_prefixes:\n  - cursor/\n"
                "deny_paths:\n  - .github/workflows/ci.yml\n"
                "docs_sync:\n"
                "  - paths: [src/**]\n"
                "    require: [CHANGELOG.md]\n",
                encoding="utf-8",
            )
            (root / "CHANGELOG.md").write_text("## [forge-1.1.0]\n\n- added\n", encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "config")
            _git(root, "checkout", "-b", "cursor/src")
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text("## [forge-1.1.0]\n\n- src\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_OK, out)
            self.assertIn("docs_sync", out)

    def test_broken_relative_link_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product(root)
            _git(root, "checkout", "-b", "cursor/docs")
            (root / "README.md").write_text("see [missing](no-such.md)\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("docs_sync", out)
            self.assertIn("no-such.md", out)

    def test_ignored_and_untracked_markdown_is_not_scanned(self) -> None:
        # node_modules / build output carry thousands of foreign READMEs with
        # relative links and pin-like strings; only tracked files are ours.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product(root)
            (root / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
            _git(root, "add", ".gitignore")
            _git(root, "commit", "-m", "ignore")
            _git(root, "checkout", "-b", "cursor/docs")
            (root / "node_modules" / "dep").mkdir(parents=True)
            (root / "node_modules" / "dep" / "README.md").write_text(
                "[x](../nope.md) overlay-v9.9.9\n", encoding="utf-8"
            )
            code, out = _check(root)
            self.assertEqual(code, EXIT_OK, out)

    def test_site_root_links_are_web_paths_not_repo_paths(self) -> None:
        # A web app links /diagram.svg meaning public/diagram.svg served at the
        # site root; that is not a repository-relative markdown link.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product(root)
            _git(root, "checkout", "-b", "cursor/docs")
            (root / "README.md").write_text("![d](/diagrams/energy.svg)\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_OK, out)

    def _init_workshop_like(self, root: Path) -> None:
        # Pin mentions are checked against this repo's own tags, so only the
        # workshop (which owns overlay-v*/forge-v*) runs that rule.
        _init_product(root)
        (root / "overlay").mkdir()
        (root / "overlay" / "__init__.py").write_text('__version__ = "0"\n', encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "workshop")

    def test_adopter_may_mention_tool_pins_it_does_not_own(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_product(root)
            _git(root, "checkout", "-b", "cursor/docs")
            (root / "README.md").write_text("pin overlay-v9.9.9 from the tool repo\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_OK, out)

    def test_unregistered_pin_mention_is_red_in_the_workshop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_workshop_like(root)
            _git(root, "checkout", "-b", "cursor/docs")
            (root / "README.md").write_text("pin overlay-v9.9.9\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("overlay-v9.9.9", out)

    def test_changelog_heading_registers_next_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_workshop_like(root)
            (root / "CHANGELOG.md").write_text("## [overlay-9.9.9]\n\nnext\n", encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "changelog")
            _git(root, "checkout", "-b", "cursor/docs")
            (root / "README.md").write_text("pin overlay-v9.9.9\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_OK, out)


if __name__ == "__main__":
    unittest.main()
