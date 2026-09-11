"""Forge status: per-ruleset installed/missing/drifted + STATE.md. Fake API only."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from forge import EXIT_OK, TAG_RULESET_NAME, branch_ruleset_name
from forge.status import EXIT_STATE, GENERATED_HEADER, MISSING_TOKEN_NOTE, run_status
from tests.forge.fake_github import FakeGitHub

FAKE_API = "https://forge.test"
REPO = "acme/widget"
SIMPLE_YAML = (
    "schema: forge-config/v1\n"
    "protect:\n"
    "  - main\n"
    "required_checks:\n"
    "  - unit\n"
)


class StatusTests(unittest.TestCase):
    def test_missing_rulesets_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(SIMPLE_YAML, encoding="utf-8")
            fake = FakeGitHub()
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = run_status(
                repo=REPO,
                urlopen=fake.urlopen,
                base_url=FAKE_API,
                stdout=stdout,
                stderr=stderr,
                environ={"FORGE_GITHUB_TOKEN": "t"},
                root=root,
            )
            self.assertEqual(code, EXIT_OK, stderr.getvalue())
            text = stdout.getvalue()
            self.assertIn(f"{branch_ruleset_name('main')}: missing", text)
            self.assertIn(f"{TAG_RULESET_NAME}: missing", text)
            self.assertEqual(fake.writes(), [])
            self.assertTrue(all(method == "GET" for method in fake.methods()))

    def test_installed_and_drifted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(SIMPLE_YAML, encoding="utf-8")
            fake = FakeGitHub()
            fake.rulesets.append(
                {
                    "id": 4,
                    "name": branch_ruleset_name("main"),
                    "target": "branch",
                    "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
                    "rules": [
                        {"type": "deletion"},
                        {"type": "non_fast_forward"},
                        {
                            "type": "pull_request",
                            "parameters": {
                                "required_approving_review_count": 1,
                                "require_code_owner_review": False,
                                "dismiss_stale_reviews_on_push": True,
                            },
                        },
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "strict_required_status_checks_policy": True,
                                "required_status_checks": [{"context": "unit"}],
                            },
                        },
                    ],
                }
            )
            fake.rulesets.append(
                {
                    "id": 5,
                    "name": TAG_RULESET_NAME,
                    "target": "tag",
                    "conditions": {"ref_name": {"include": ["refs/tags/other-*"], "exclude": []}},
                    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
                }
            )
            stdout = io.StringIO()
            code = run_status(
                repo=REPO,
                urlopen=fake.urlopen,
                base_url=FAKE_API,
                stdout=stdout,
                stderr=io.StringIO(),
                environ={"GITHUB_TOKEN": "t"},
                root=root,
            )
            self.assertEqual(code, EXIT_OK)
            text = stdout.getvalue()
            self.assertIn(f"{branch_ruleset_name('main')}: installed", text)
            self.assertIn(f"{TAG_RULESET_NAME}: drifted", text)

    def test_missing_token_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(SIMPLE_YAML, encoding="utf-8")
            fake = FakeGitHub()
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = run_status(
                repo=REPO,
                urlopen=fake.urlopen,
                base_url=FAKE_API,
                stdout=stdout,
                stderr=stderr,
                environ={},
                root=root,
            )
            self.assertEqual(code, EXIT_OK, stderr.getvalue())
            self.assertIn(MISSING_TOKEN_NOTE, stdout.getvalue())
            self.assertEqual(fake.calls, [])

    def test_write_state_and_check_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(SIMPLE_YAML, encoding="utf-8")
            (root / "docs").mkdir()
            stdout = io.StringIO()
            code = run_status(
                repo=REPO,
                urlopen=FakeGitHub().urlopen,
                base_url=FAKE_API,
                stdout=stdout,
                stderr=io.StringIO(),
                environ={},
                root=root,
                write="docs/STATE.md",
            )
            self.assertEqual(code, EXIT_OK)
            text = (root / "docs" / "STATE.md").read_text(encoding="utf-8")
            self.assertIn(GENERATED_HEADER, text)
            self.assertIn("保护分支", text)
            self.assertIn(MISSING_TOKEN_NOTE, text)
            stdout2 = io.StringIO()
            stderr = io.StringIO()
            code = run_status(
                repo=REPO,
                urlopen=FakeGitHub().urlopen,
                base_url=FAKE_API,
                stdout=stdout2,
                stderr=stderr,
                environ={},
                root=root,
                check_state=True,
            )
            self.assertEqual(code, EXIT_OK, stderr.getvalue())
            self.assertIn("docs/STATE.md: ok", stdout2.getvalue())

    def test_state_written_before_the_release_tag_stays_fresh(self) -> None:
        # The release commit carries STATE.md and is then tagged; the tag must
        # not make the STATE it contains stale, or every release is red.
        import os
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}

            def git(*args: str) -> None:
                subprocess.run(["git", "-C", str(root), "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, env=env)

            (root / "forge.yaml").write_text(SIMPLE_YAML, encoding="utf-8")
            (root / "docs").mkdir()
            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@example.test")
            git("config", "user.name", "T")
            git("add", "-A")
            git("commit", "-q", "-m", "init")
            git("tag", "-a", "forge-v1.0.0", "-m", "old")
            code = run_status(
                repo=REPO, urlopen=FakeGitHub().urlopen, base_url=FAKE_API, stdout=io.StringIO(),
                stderr=io.StringIO(), environ={}, root=root, write="docs/STATE.md",
            )
            self.assertEqual(code, EXIT_OK)
            git("add", "-A")
            git("commit", "-q", "-m", "release")
            git("tag", "-a", "forge-v1.1.0", "-m", "new")
            stderr = io.StringIO()
            code = run_status(
                repo=REPO, urlopen=FakeGitHub().urlopen, base_url=FAKE_API, stdout=io.StringIO(),
                stderr=stderr, environ={}, root=root, check_state=True,
            )
            self.assertEqual(code, EXIT_OK, stderr.getvalue())

    def test_ci_job_names_exclude_workflow_and_step_names(self) -> None:
        from forge.status import scan_ci_job_names

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wf = root / ".github" / "workflows"
            wf.mkdir(parents=True)
            (wf / "ci.yml").write_text(
                "name: ci\non: push\njobs:\n  unit:\n    name: unit\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - name: Checkout\n        uses: actions/checkout@v4\n"
                "  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - run: true\n",
                encoding="utf-8",
            )
            self.assertEqual(scan_ci_job_names(root), ["unit", "lint"])

    def test_check_state_missing_file_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(SIMPLE_YAML, encoding="utf-8")
            stderr = io.StringIO()
            code = run_status(
                repo=REPO,
                urlopen=FakeGitHub().urlopen,
                base_url=FAKE_API,
                stdout=io.StringIO(),
                stderr=stderr,
                environ={},
                root=root,
                check_state=True,
            )
            self.assertEqual(code, EXIT_STATE)
            self.assertIn("forge status --write", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
