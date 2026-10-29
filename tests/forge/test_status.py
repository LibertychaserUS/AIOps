"""Forge status: per-ruleset installed/missing/drifted + STATE.md. Fake API only."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from forge.status import EXIT_STATE, GENERATED_HEADER, MISSING_TOKEN_NOTE, run_status

from forge import EXIT_OK, TAG_RULESET_NAME, branch_ruleset_name
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
                    "enforcement": "active",
                    "bypass_actors": [],
                    "source_type": "Repository",
                    "node_id": "RRS_x",
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
                                "require_last_push_approval": True,
                                "allowed_merge_methods": ["squash"],
                                "required_review_thread_resolution": False,
                                # echoed by GitHub, never sent by Forge: not drift
                                "automatic_copilot_code_review_enabled": False,
                            },
                        },
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "strict_required_status_checks_policy": True,
                                "do_not_enforce_on_create": False,
                                "required_status_checks": [{"context": "unit", "integration_id": 15368}],
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


class StaleAndWarningTests(unittest.TestCase):
    def test_stale_forge_rulesets_are_listed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(SIMPLE_YAML, encoding="utf-8")
            fake = FakeGitHub()
            fake.rulesets.append(
                {"id": 9, "name": branch_ruleset_name("release"), "target": "branch", "rules": []}
            )
            fake.rulesets.append({"id": 10, "name": "someone-elses-rule", "target": "branch", "rules": []})
            code, out, err = _status(fake, root)
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn(f"{branch_ruleset_name('main')}: missing", out)
            self.assertIn(f"{branch_ruleset_name('release')}: stale", out)
            self.assertNotIn("someone-elses-rule", out)
            self.assertEqual(fake.writes(), [])

    def test_code_owners_without_file_warns_on_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(
                SIMPLE_YAML + "review:\n  min_approvals: 1\n  code_owners: true\n", encoding="utf-8"
            )
            code, _out, err = _status(FakeGitHub(), root)
            self.assertEqual(code, EXIT_OK)
            self.assertIn("warning: code_owners: true but no CODEOWNERS", err)
            (root / ".github").mkdir()
            (root / ".github" / "CODEOWNERS").write_text("* @acme/owners\n", encoding="utf-8")
            code, _out, err = _status(FakeGitHub(), root)
            self.assertEqual(code, EXIT_OK)
            self.assertNotIn("warning", err)


if __name__ == "__main__":
    unittest.main()


def _status(fake: FakeGitHub, root: Path, **kwargs):
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = run_status(
        repo=REPO,
        urlopen=fake.urlopen,
        base_url=FAKE_API,
        stdout=stdout,
        stderr=stderr,
        environ=kwargs.pop("environ", {"GITHUB_TOKEN": "t"}),
        root=root,
        **kwargs,
    )
    return code, stdout.getvalue(), stderr.getvalue()


class StatusDriftTests(unittest.TestCase):
    def _applied(self, root: Path) -> FakeGitHub:
        from forge.apply import run_apply

        (root / "forge.yaml").write_text(SIMPLE_YAML, encoding="utf-8")
        fake = FakeGitHub()
        code = run_apply(
            repo=REPO,
            path=root / "forge.yaml",
            token="t",
            urlopen=fake.urlopen,
            base_url=FAKE_API,
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
        self.assertEqual(code, EXIT_OK)
        return fake

    def test_fresh_apply_is_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = self._applied(root)
            for item in fake.rulesets:
                item.update(
                    {
                        "source_type": "Repository",
                        "source": REPO,
                        "node_id": "RRS_1",
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                        "_links": {"self": {"href": "x"}},
                        "current_user_can_bypass": "never",
                    }
                )
            code, out, err = _status(fake, root)
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn(f"{branch_ruleset_name('main')}: installed", out)
            self.assertIn(f"{TAG_RULESET_NAME}: installed", out)

    def test_weakened_live_rulesets_are_drifted(self) -> None:
        tampers = {
            "enforcement": lambda rs: rs.update(enforcement="disabled"),
            "evaluate": lambda rs: rs.update(enforcement="evaluate"),
            "bypass": lambda rs: rs.update(
                bypass_actors=[{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
            ),
            "exclude": lambda rs: rs["conditions"]["ref_name"].update(exclude=["~ALL"]),
            "last_push": lambda rs: [
                rule["parameters"].update(require_last_push_approval=False)
                for rule in rs["rules"]
                if rule["type"] == "pull_request"
            ],
            "merge_methods": lambda rs: [
                rule["parameters"].update(allowed_merge_methods=["merge", "squash", "rebase"])
                for rule in rs["rules"]
                if rule["type"] == "pull_request"
            ],
            "unbound_check": lambda rs: [
                rule["parameters"].update(
                    required_status_checks=[
                        {"context": c["context"]} for c in rule["parameters"]["required_status_checks"]
                    ]
                )
                for rule in rs["rules"]
                if rule["type"] == "required_status_checks"
            ],
            "integration_id": lambda rs: [
                rule["parameters"].update(
                    required_status_checks=[
                        {"context": c["context"], "integration_id": 999}
                        for c in rule["parameters"]["required_status_checks"]
                    ]
                )
                for rule in rs["rules"]
                if rule["type"] == "required_status_checks"
            ],
            "extra_rule": lambda rs: rs["rules"].append({"type": "update"}),
        }
        for label, tamper in tampers.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                fake = self._applied(root)
                main = next(rs for rs in fake.rulesets if rs["name"] == branch_ruleset_name("main"))
                tamper(main)
                code, out, err = _status(fake, root)
                self.assertEqual(code, EXIT_OK, err)
                self.assertIn(f"{branch_ruleset_name('main')}: drifted", out)
                self.assertIn(f"{TAG_RULESET_NAME}: installed", out)

    def test_check_order_does_not_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(
                "schema: forge-config/v1\nprotect: [main]\nrequired_checks: [unit, lint]\n",
                encoding="utf-8",
            )
            from forge.apply import run_apply

            fake = FakeGitHub()
            run_apply(
                repo=REPO, path=root / "forge.yaml", token="t", urlopen=fake.urlopen,
                base_url=FAKE_API, stdout=io.StringIO(), stderr=io.StringIO(),
            )
            for rs in fake.rulesets:
                for rule in rs["rules"]:
                    if rule["type"] == "required_status_checks":
                        rule["parameters"]["required_status_checks"].reverse()
            code, out, _ = _status(fake, root)
            self.assertIn(f"{branch_ruleset_name('main')}: installed", out)

    def test_paged_listing_finds_rulesets_past_page_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = FakeGitHub()
            fake.rulesets.extend(
                {"id": 1000 + i, "name": f"other-{i}", "target": "branch", "rules": []}
                for i in range(5)
            )
            fake.next_id = 2000
            (root / "forge.yaml").write_text(SIMPLE_YAML, encoding="utf-8")
            from forge.apply import run_apply

            run_apply(
                repo=REPO, path=root / "forge.yaml", token="t", urlopen=fake.urlopen,
                base_url=FAKE_API, stdout=io.StringIO(), stderr=io.StringIO(),
            )
            fake.ruleset_page_size = 2
            code, out, err = _status(fake, root)
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn(f"{branch_ruleset_name('main')}: installed", out)
            self.assertIn(f"{TAG_RULESET_NAME}: installed", out)


class StatusConfigPathTests(unittest.TestCase):
    def test_explicit_missing_path_is_exit_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = _status(FakeGitHub(), Path(tmp), path=Path(tmp) / "nope.yaml", environ={})
            self.assertEqual(code, 3)
            self.assertIn("not found", err)

    def test_default_path_is_root_not_cwd(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as cwd:
            Path(cwd, "forge.yaml").write_text(
                "schema: forge-config/v1\nprotect: [elsewhere]\n", encoding="utf-8"
            )
            old = os.getcwd()
            os.chdir(cwd)
            try:
                code, out, err = _status(FakeGitHub(), Path(tmp), environ={})
            finally:
                os.chdir(old)
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn(branch_ruleset_name("main"), out)
            self.assertNotIn("elsewhere", out)


class CheckStateRuleTests(unittest.TestCase):
    YAML = (
        "schema: forge-config/v1\nprotect:\n  - dev\n  - main\nbranches:\n"
        "  dev:\n    required_checks: [unit]\n    approvals: 0\n"
        "  main:\n    required_checks: [unit]\n    approvals: 1\n    code_owners: true\n"
        "    promote_from: dev\n"
    )

    def test_rule_changes_make_state_stale(self) -> None:
        edits = {
            "approvals": ("    approvals: 1\n", "    approvals: 2\n"),
            "code_owners": ("    code_owners: true\n", "    code_owners: false\n"),
            "promote_from": ("    promote_from: dev\n", ""),
        }
        for label, (old, new) in edits.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "forge.yaml").write_text(self.YAML, encoding="utf-8")
                code, _, err = _status(FakeGitHub(), root, environ={}, write="docs/STATE.md")
                self.assertEqual(code, EXIT_OK, err)
                code, _, err = _status(FakeGitHub(), root, environ={}, check_state=True)
                self.assertEqual(code, EXIT_OK, err)
                (root / "forge.yaml").write_text(self.YAML.replace(old, new), encoding="utf-8")
                code, _, err = _status(FakeGitHub(), root, environ={}, check_state=True)
                self.assertEqual(code, EXIT_STATE, label)
                self.assertIn("保护分支", err)
