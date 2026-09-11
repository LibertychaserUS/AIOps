"""forge promote against FakeGitHub. Never merges."""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from forge import EXIT_AUTH, EXIT_CONFIG, EXIT_OK, SUBMIT_TOKEN_ENV
from forge.promote import run_promote
from forge.submit import BODY_HEADINGS, MISSING_SUBMIT_TOKEN
from tests.forge.fake_github import FakeGitHub

FAKE_API = "https://forge.test"
REPO = "acme/widget"
YAML = (
    "schema: forge-config/v1\n"
    "protect:\n"
    "  - dev\n"
    "  - main\n"
    "branches:\n"
    "  dev:\n"
    "    required_checks: [unit]\n"
    "    approvals: 0\n"
    "    code_owners: false\n"
    "  main:\n"
    "    required_checks: [unit, forge-check]\n"
    "    approvals: 1\n"
    "    code_owners: true\n"
    "    promote_from: dev\n"
    "title:\n"
    "  scopes:\n"
    "    - overlay/agent\n"
    "    - forge/agent\n"
)


def _git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        env=env,
    )


def _repo(tmp: str) -> Path:
    root = Path(tmp)
    (root / "forge.yaml").write_text(YAML, encoding="utf-8")
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.test")
    _git(root, "config", "user.name", "T")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", "dev")
    (root / "README.md").write_text("hello dev\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "feat(overlay/agent): land on dev")
    return root


def _promote(**kwargs):
    fake = kwargs.pop("fake", FakeGitHub())
    stdout = kwargs.pop("stdout", io.StringIO())
    stderr = kwargs.pop("stderr", io.StringIO())
    env = kwargs.pop("environ", {SUBMIT_TOKEN_ENV: "test-token"})
    code = run_promote(
        repo=kwargs.pop("repo", REPO),
        from_branch=kwargs.pop("from_branch", "dev"),
        to_branch=kwargs.pop("to_branch", "main"),
        urlopen=fake.urlopen,
        base_url=FAKE_API,
        stdout=stdout,
        stderr=stderr,
        environ=env,
        **kwargs,
    )
    return code, stdout.getvalue(), stderr.getvalue(), fake


class PromoteTests(unittest.TestCase):
    def test_dry_run_requires_token_and_never_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            code, out, err, fake = _promote(
                path=root / "forge.yaml",
                cwd=root,
                dry_run=True,
                environ={},
            )
            self.assertEqual(code, EXIT_AUTH)
            self.assertIn("dry-run", out)
            self.assertIn(MISSING_SUBMIT_TOKEN, err)
            self.assertIn("title:", out)
            self.assertIn("promote dev", out)
            for heading in BODY_HEADINGS:
                self.assertIn(heading, out)
            self.assertEqual(fake.writes(), [])

    def test_opens_non_draft_pr_and_never_merges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            fake = FakeGitHub()
            code, out, err, _ = _promote(
                fake=fake,
                path=root / "forge.yaml",
                cwd=root,
            )
            self.assertEqual(code, EXIT_OK, err)
            self.assertEqual(len(fake.pulls), 1)
            self.assertFalse(fake.pulls[0]["draft"])
            self.assertEqual(fake.pulls[0]["head"]["ref"], "dev")
            self.assertEqual(fake.pulls[0]["base"]["ref"], "main")
            self.assertIn("opened promote PR #1", out)
            self.assertIn("chore(overlay/agent):", fake.pulls[0]["title"])
            self.assertIn("## 做了什么", fake.pulls[0]["body"])
            self.assertIn("feat(overlay/agent): land on dev", fake.pulls[0]["body"])
            self.assertFalse(any("/merge" in path for _m, path, _b in fake.calls))

    def test_second_promote_patches_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            fake = FakeGitHub()
            first, _, err1, _ = _promote(fake=fake, path=root / "forge.yaml", cwd=root)
            self.assertEqual(first, EXIT_OK, err1)
            second, out2, err2, _ = _promote(fake=fake, path=root / "forge.yaml", cwd=root)
            self.assertEqual(second, EXIT_OK, err2)
            self.assertEqual(fake.methods().count("POST"), 1)
            self.assertEqual(fake.methods().count("PATCH"), 1)
            self.assertIn("updated promote PR #1", out2)
            self.assertEqual(len(fake.pulls), 1)

    def test_wrong_promote_from_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            code, _, err, fake = _promote(
                path=root / "forge.yaml",
                cwd=root,
                from_branch="cursor/x",
                dry_run=True,
                environ={SUBMIT_TOKEN_ENV: "t"},
            )
            self.assertEqual(code, EXIT_CONFIG)
            self.assertIn("promote_from", err)
            self.assertEqual(fake.calls, [])

    def test_scopes_any_uses_release_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            yaml = YAML.replace(
                "title:\n  scopes:\n    - overlay/agent\n    - forge/agent\n",
                "title:\n  scopes: any\n",
            )
            (root / "forge.yaml").write_text(yaml, encoding="utf-8")
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.test")
            _git(root, "config", "user.name", "T")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init")
            _git(root, "checkout", "-b", "dev")
            (root / "README.md").write_text("hello2\n", encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "feat: land")
            code, out, err, _ = _promote(
                path=root / "forge.yaml",
                cwd=root,
                dry_run=True,
            )
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn("chore(release/agent):", out)


if __name__ == "__main__":
    unittest.main()
