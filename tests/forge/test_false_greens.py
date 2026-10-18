"""forge check / ci-select false greens: each case was green before the fix."""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from forge.apply import ForgeError, load_config
from forge.check import (
    EXIT_CHECK,
    deny_paths_step,
    path_matches_pattern,
    run_check,
    suite_guard_step,
)
from forge.ci_select import git_changed, load_ci_config, select_products
from forge.title import EXAMPLE, run_pr_title

from forge import EXIT_CONFIG, EXIT_OK

ACTIVE = "id: login\nstatus: active\nproduct_command: true\n"
BLOCKED = "id: login\nstatus: blocked\nblocked_reason: parked https://example.test/OF-1\nproduct_command: true\n"
FORGE_YAML = (
    "schema: forge-config/v1\n"
    "protect:\n  - dev\n"
    "agent_branch_prefixes:\n  - agent/\n"
    "deny_paths:\n  - .github/workflows/release.yml\n  - secret/\n  - '**/*.pem'\n"
    "docs_sync:\n"
    "  - paths: [forge/**/*.py]\n"
    "    require: [CHANGELOG.md]\n"
)


def _git(root: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    proc = subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.stdout


def _init(root: Path, branch: str = "dev", forge_yaml: str = FORGE_YAML) -> None:
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "release.yml").write_text("name: r\n", encoding="utf-8")
    (root / "suites" / "login").mkdir(parents=True)
    (root / "suites" / "login" / "suite.yaml").write_text(ACTIVE, encoding="utf-8")
    (root / "forge").mkdir()
    (root / "forge" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text("c\n", encoding="utf-8")
    (root / "forge.yaml").write_text(forge_yaml, encoding="utf-8")
    _git(root, "init", "-q", "-b", branch)
    _git(root, "config", "user.email", "t@example.test")
    _git(root, "config", "user.name", "T")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")


def _check(root: Path, environ: dict[str, str] | None = None, **kwargs) -> tuple[int, str]:
    stdout = io.StringIO()
    code = run_check(
        root,
        title=EXAMPLE,
        stdout=stdout,
        stderr=io.StringIO(),
        environ=environ or {},
        run_unittests=False,
        **kwargs,
    )
    return code, stdout.getvalue()


class NoBaseRefTests(unittest.TestCase):
    def test_single_branch_clone_without_protect_ref_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init(root, branch="agent/x")
            (root / "forge" / "x.py").write_text("x = 2\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_CHECK, out)
            for step in ("deny_paths", "suite_guard", "docs_sync"):
                line = next(row for row in out.splitlines() if row.strip().startswith(step))
                self.assertIn("FAIL", line, out)
                self.assertIn("git fetch origin dev", line, out)

    def test_github_base_ref_is_the_last_resort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            remote = Path(tmp) / "remote.git"
            remote.mkdir()
            _git(remote, "init", "-q", "--bare", "-b", "trunk")
            seed = Path(tmp) / "seed"
            seed.mkdir()
            _init(seed, branch="trunk")
            _git(seed, "remote", "add", "origin", str(remote))
            _git(seed, "push", "-q", "origin", "trunk")
            root = Path(tmp) / "clone"
            _git(Path(tmp), "clone", "-q", str(remote), str(root))
            _git(root, "checkout", "-q", "-b", "agent/y")
            _git(root, "branch", "-q", "-D", "trunk")
            code, out = _check(root, {"GITHUB_BASE_REF": "trunk"})
            self.assertEqual(code, EXIT_OK, out)
            self.assertIn("vs refs/remotes/origin/trunk", out)


class CommittedDiffTests(unittest.TestCase):
    def test_staged_revert_does_not_hide_committed_deny_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init(root)
            _git(root, "checkout", "-q", "-b", "agent/ci")
            (root / ".github" / "workflows" / "release.yml").write_text("name: x\n", encoding="utf-8")
            _git(root, "commit", "-qam", "touch release")
            _git(root, "checkout", "dev", "--", ".github/workflows/release.yml")
            code, out = _check(root)
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("diff touches .github/workflows/release.yml", out)


class BranchResolutionTests(unittest.TestCase):
    def _blocked_commit(self, root: Path) -> None:
        _init(root)
        _git(root, "checkout", "-q", "-b", "agent/block")
        (root / "suites" / "login" / "suite.yaml").write_text(BLOCKED, encoding="utf-8")
        _git(root, "commit", "-qam", "block")

    def test_detached_head_without_env_is_an_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._blocked_commit(root)
            _git(root, "checkout", "-q", "--detach")
            step = suite_guard_step(root, environ={})
            self.assertEqual(step.status, "fail", step.detail)
            self.assertIn("detached HEAD", step.detail)

    def test_explicit_head_branch_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._blocked_commit(root)
            _git(root, "checkout", "-q", "-b", "review/block")
            human = suite_guard_step(root, environ={})
            self.assertEqual(human.status, "ok", human.detail)
            code, out = _check(root, head_branch="agent/block")
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("agent branch agent/block must not set or clear blocked", out)


class NonAsciiPathTests(unittest.TestCase):
    def test_non_ascii_deny_path_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init(root)
            _git(root, "checkout", "-q", "-b", "agent/k")
            (root / "secret").mkdir()
            (root / "secret" / "密钥.txt").write_text("k\n", encoding="utf-8")
            step = deny_paths_step(root, environ={})
            self.assertEqual(step.status, "fail", step.detail)
            self.assertIn("secret/密钥.txt", step.detail)

    def test_non_ascii_suite_is_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init(root)
            (root / "suites" / "中").mkdir()
            (root / "suites" / "中" / "suite.yaml").write_text(ACTIVE, encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-qm", "zh suite")
            _git(root, "checkout", "-q", "-b", "agent/zh")
            (root / "suites" / "中" / "suite.yaml").write_text(BLOCKED, encoding="utf-8")
            step = suite_guard_step(root, environ={})
            self.assertEqual(step.status, "fail", step.detail)
            self.assertIn("suites/中/suite.yaml", step.detail)

    def test_non_ascii_markdown_links_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init(root)
            (root / "文档").mkdir()
            (root / "文档" / "说明.md").write_text("[x](不存在.md)\n", encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-qm", "zh doc")
            code, out = _check(root)
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("不存在.md", out)


class GlobTests(unittest.TestCase):
    def test_matcher_semantics(self) -> None:
        cases = [
            ("forge/x.py", "forge/**/*.py", True),
            ("forge/a/b.py", "forge/**/*.py", True),
            ("forge/a/b.txt", "forge/**/*.py", False),
            ("src/a/b.py", "src/*.py", False),
            ("src/b.py", "src/*.py", True),
            ("forge", "forge/**", True),
            ("forgery/x", "forge/**", False),
            ("a/b/key.pem", "*.pem", True),
            ("secret/a.txt", "secret/", True),
            ("secrets/a.txt", "secret/", False),
            ("docs/locked/a.md", "docs/locked", True),
            (".github/workflows/ci.yml.bak", ".github/workflows/ci.yml", False),
        ]
        for path, pattern, want in cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertIs(path_matches_pattern(path, pattern), want)

    def test_deny_paths_globstar_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init(root)
            _git(root, "checkout", "-q", "-b", "agent/pem")
            (root / "a" / "b").mkdir(parents=True)
            (root / "a" / "b" / "key.pem").write_text("k\n", encoding="utf-8")
            step = deny_paths_step(root, environ={})
            self.assertEqual(step.status, "fail", step.detail)
            self.assertIn("a/b/key.pem", step.detail)

    def test_docs_sync_star_does_not_cross_slash(self) -> None:
        yaml = FORGE_YAML.replace("forge/**/*.py", "src/*.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init(root, forge_yaml=yaml)
            _git(root, "checkout", "-q", "-b", "agent/deep")
            (root / "src" / "a").mkdir(parents=True)
            (root / "src" / "a" / "b.py").write_text("b = 1\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_OK, out)

    def test_docs_sync_globstar_hits_top_level_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init(root)
            _git(root, "checkout", "-q", "-b", "agent/top")
            (root / "forge" / "x.py").write_text("x = 3\n", encoding="utf-8")
            code, out = _check(root)
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("missing CHANGELOG.md", out)


class CiSelectTests(unittest.TestCase):
    def _repo(self, top: Path) -> None:
        _git(top, "init", "-q", "-b", "dev")
        _git(top, "config", "user.email", "t@example.test")
        _git(top, "config", "user.name", "T")

    def test_move_out_of_product_keeps_old_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "forge").mkdir()
            (root / "forge" / "a.py").write_text("a = 1\n" * 20, encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-qm", "a")
            (root / "other").mkdir()
            _git(root, "mv", "forge/a.py", "other/a.py")
            _git(root, "commit", "-qm", "move")
            changed = git_changed(root)
            self.assertIn("forge/a.py", changed or [])

    def test_monorepo_root_paths_are_relative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp)
            self._repo(top)
            product = top / "svc"
            (product / "forge").mkdir(parents=True)
            (product / "forge" / "a.py").write_text("a = 1\n", encoding="utf-8")
            (top / "top.txt").write_text("t\n", encoding="utf-8")
            _git(top, "add", "-A")
            _git(top, "commit", "-qm", "a")
            (product / "forge" / "a.py").write_text("a = 2\n", encoding="utf-8")
            (top / "top.txt").write_text("t2\n", encoding="utf-8")
            _git(top, "commit", "-qam", "b")
            self.assertEqual(git_changed(product), ["forge/a.py"])

    def test_unknown_paths_run_all_even_with_title(self) -> None:
        root = Path(__file__).resolve().parents[2]
        config = load_ci_config(root)
        products, reason, _source = select_products(config, title="docs(docs/dev): x", changed=None)
        self.assertEqual(reason, "undecided-run-all")
        self.assertEqual(set(products), {"overlay", "forge"})

    def _ci_yaml(self, ci: str) -> str:
        return "schema: forge-config/v1\nprotect:\n  - dev\nci:\n" + ci

    def test_unknown_ci_keys_exit_3(self) -> None:
        bad = {
            "  produts:\n    forge:\n      check: forge-check\n": "ci.produts; did you mean products",
            "  products:\n    forge:\n      chek: forge-check\n": "ci.products.forge.chek; did you mean check",
            "  select:\n    titel:\n      docs: []\n": "ci.select.titel; did you mean title",
        }
        for body, needle in bad.items():
            with self.subTest(needle=needle), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "forge.yaml").write_text(self._ci_yaml(body), encoding="utf-8")
                with self.assertRaises(ForgeError) as ctx:
                    load_config(root / "forge.yaml")
                self.assertEqual(ctx.exception.code, EXIT_CONFIG)
                self.assertIn(needle, ctx.exception.message)
                with self.assertRaises(ForgeError):
                    load_ci_config(root)


class ConfigLoadTests(unittest.TestCase):
    def test_duplicate_keys_are_refused(self) -> None:
        texts = (
            "schema: forge-config/v1\nprotect:\n  - dev\nprotect:\n  - main\n",
            "schema: forge-config/v1\ndocs_sync:\n  - paths: [a/]\n    require: [B.md]\n    paths: [c/]\n",
        )
        for text in texts:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "forge.yaml"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ForgeError) as ctx:
                    load_config(path)
                self.assertEqual(ctx.exception.code, EXIT_CONFIG)
                self.assertIn("duplicate key", ctx.exception.message)

    def test_pr_title_refuses_unloadable_forge_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(
                "schema: forge-config/v1\ntitle:\n  scopes: [docs/dev]\nprotekt:\n  - dev\n",
                encoding="utf-8",
            )
            stderr = io.StringIO()
            code = run_pr_title(title=EXAMPLE, environ={}, stderr=stderr, root=root)
            self.assertEqual(code, EXIT_CONFIG)
            self.assertIn("protekt", stderr.getvalue())


class GitMissingTests(unittest.TestCase):
    def test_missing_git_fails_the_git_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(FORGE_YAML, encoding="utf-8")
            with mock.patch("forge.check.subprocess.run", side_effect=FileNotFoundError("git")):
                code, out = _check(root)
            self.assertEqual(code, EXIT_CHECK, out)
            self.assertIn("cannot run git", out)


if __name__ == "__main__":
    unittest.main()
