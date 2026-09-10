"""Forge apply against a fake Rulesets API. Never talks to a real repo."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from forge import COPY_FILES_NOTE, EXIT_API, EXIT_AUTH, EXIT_CONFIG, EXIT_OK, RULESET_NAME
from forge.apply import build_payload, load_config, load_ruleset_template, run_apply, validate_config
from forge.__main__ import main

from tests.forge.fake_github import FakeGitHub

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "forge" / "forge.example.yaml"
LG_EXAMPLE = ROOT / "examples" / "learning-guide" / "forge.yaml"
FAKE_API = "https://forge.test"
REPO = "acme/widget"


def _apply(**kwargs):
    fake = kwargs.pop("fake", FakeGitHub())
    stdout = kwargs.pop("stdout", io.StringIO())
    stderr = kwargs.pop("stderr", io.StringIO())
    env = kwargs.pop("environ", {"FORGE_GITHUB_TOKEN": "test-token"})
    code = run_apply(
        repo=kwargs.pop("repo", REPO),
        urlopen=fake.urlopen,
        base_url=FAKE_API,
        stdout=stdout,
        stderr=stderr,
        environ=env,
        **kwargs,
    )
    return code, stdout.getvalue(), stderr.getvalue(), fake


class ApplyIdempotencyTests(unittest.TestCase):
    def test_missing_ruleset_posts_then_put_on_second_apply(self) -> None:
        fake = FakeGitHub()
        first, out1, err1, _ = _apply(fake=fake)
        self.assertEqual(first, EXIT_OK, err1)
        self.assertEqual(fake.methods().count("POST"), 1)
        self.assertEqual(fake.methods().count("PUT"), 0)
        self.assertIn("created ruleset id=1", out1)
        self.assertIn("protect: main", out1)
        self.assertIn(COPY_FILES_NOTE.splitlines()[0], out1)

        second, out2, err2, _ = _apply(fake=fake)
        self.assertEqual(second, EXIT_OK, err2)
        self.assertEqual(fake.methods().count("POST"), 1)
        self.assertEqual(fake.methods().count("PUT"), 1)
        self.assertIn("updated ruleset id=1", out2)
        self.assertEqual(len(fake.rulesets), 1)
        self.assertEqual(fake.rulesets[0]["name"], RULESET_NAME)

    def test_existing_same_name_puts_without_post(self) -> None:
        fake = FakeGitHub()
        fake.rulesets.append({"id": 9, "name": RULESET_NAME})
        fake.next_id = 10
        code, out, err, _ = _apply(fake=fake)
        self.assertEqual(code, EXIT_OK, err)
        self.assertEqual(fake.methods().count("POST"), 0)
        self.assertEqual(fake.methods().count("PUT"), 1)
        self.assertIn("updated ruleset id=9", out)

    def test_other_ruleset_name_still_posts(self) -> None:
        fake = FakeGitHub()
        fake.rulesets.append({"id": 3, "name": "someone-else"})
        code, _, err, _ = _apply(fake=fake)
        self.assertEqual(code, EXIT_OK, err)
        self.assertEqual(fake.methods().count("POST"), 1)
        self.assertEqual(fake.methods().count("PUT"), 0)


class DefaultPayloadTests(unittest.TestCase):
    def test_default_json_protects_main_requires_pr_empty_bypass(self) -> None:
        template = load_ruleset_template()
        self.assertEqual(template["name"], RULESET_NAME)
        self.assertEqual(template["bypass_actors"], [])
        include = template["conditions"]["ref_name"]["include"]
        self.assertEqual(include, ["refs/heads/main"])
        types = [rule["type"] for rule in template["rules"]]
        self.assertIn("deletion", types)
        self.assertIn("non_fast_forward", types)
        self.assertIn("pull_request", types)
        pr = next(rule for rule in template["rules"] if rule["type"] == "pull_request")
        self.assertGreaterEqual(pr["parameters"]["required_approving_review_count"], 1)
        self.assertFalse(pr["parameters"]["require_code_owner_review"])

        payload = build_payload(load_config(None))
        self.assertEqual(payload["name"], RULESET_NAME)
        self.assertEqual(payload["bypass_actors"], [])
        self.assertEqual(payload["conditions"]["ref_name"]["include"], ["refs/heads/main"])
        self.assertEqual(payload["conditions"]["ref_name"]["exclude"], [])
        pr = next(rule for rule in payload["rules"] if rule["type"] == "pull_request")
        self.assertEqual(pr["parameters"]["required_approving_review_count"], 1)
        self.assertIs(pr["parameters"]["require_code_owner_review"], False)
        self.assertIs(pr["parameters"]["dismiss_stale_reviews_on_push"], True)

    def test_example_yaml_uses_defaults_and_does_not_add_required_checks_rule(self) -> None:
        config = load_config(EXAMPLE)
        self.assertEqual(config.protect, ["main"])
        self.assertEqual(config.min_approvals, 1)
        self.assertIs(config.code_owners, False)
        payload = build_payload(config)
        types = [rule["type"] for rule in payload["rules"]]
        self.assertNotIn("required_status_checks", types)
        lg = load_config(LG_EXAMPLE)
        self.assertEqual(lg.protect, ["main"])
        self.assertIn(".github/workflows/ci.yml", lg.deny_paths)

    def test_missing_fields_use_defaults(self) -> None:
        config = validate_config({"schema": "forge-config/v1"})
        self.assertEqual(config.protect, ["main"])
        self.assertEqual(config.min_approvals, 1)
        self.assertIs(config.code_owners, False)
        self.assertEqual(config.agent_branch_prefixes, ["cursor/", "copilot/"])


class IllegalConfigTests(unittest.TestCase):
    def test_illegal_schema_enum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forge.yaml"
            path.write_text("schema: overlay-config/v1\nprotect:\n  - main\n", encoding="utf-8")
            code, _, err, fake = _apply(path=path, environ={"FORGE_GITHUB_TOKEN": "t"})
            self.assertEqual(code, EXIT_CONFIG)
            self.assertIn("illegal schema", err)
            self.assertEqual(fake.writes(), [])

    def test_illegal_protect_scalar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text("schema: forge-config/v1\nprotect: main\n", encoding="utf-8")
            code, _, err, fake = _apply(path=path)
            self.assertEqual(code, EXIT_CONFIG)
            self.assertIn("illegal protect", err)
            self.assertEqual(fake.calls, [])

    def test_illegal_code_owners_enum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text(
                "schema: forge-config/v1\nreview:\n  code_owners: maybe\n",
                encoding="utf-8",
            )
            code, _, err, fake = _apply(path=path)
            self.assertEqual(code, EXIT_CONFIG)
            self.assertIn("illegal review.code_owners", err)
            self.assertEqual(fake.writes(), [])

    def test_missing_path_is_config_error(self) -> None:
        code, _, err, fake = _apply(path=Path("/tmp/forge-does-not-exist-test.yaml"))
        self.assertEqual(code, EXIT_CONFIG)
        self.assertIn("not found", err)
        self.assertEqual(fake.calls, [])


class DryRunAndAuthTests(unittest.TestCase):
    def test_dry_run_prints_payload_and_does_not_write(self) -> None:
        fake = FakeGitHub()
        code, out, err, _ = _apply(fake=fake, dry_run=True, environ={})
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("dry-run", out)
        payload = json.loads(out.split("dry-run", 1)[1].split("protect:", 1)[0])
        self.assertEqual(payload["name"], RULESET_NAME)
        self.assertEqual(payload["bypass_actors"], [])
        self.assertEqual(payload["conditions"]["ref_name"]["include"], ["refs/heads/main"])
        self.assertIn("copy these files", out)
        self.assertEqual(fake.calls, [])
        self.assertEqual(fake.writes(), [])

    def test_missing_token_exits_2_without_write(self) -> None:
        code, _, err, fake = _apply(environ={})
        self.assertEqual(code, EXIT_AUTH)
        self.assertIn("missing", err)
        self.assertEqual(fake.calls, [])

    def test_cli_dry_run_does_not_call_write_endpoints(self) -> None:
        fake = FakeGitHub()
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["apply", "--repo", REPO, "--dry-run"],
            urlopen=fake.urlopen,
            environ={},
            stdout=stdout,
            stderr=stderr,
            base_url=FAKE_API,
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertIn("dry-run", stdout.getvalue())
        self.assertEqual(fake.writes(), [])
        self.assertEqual(fake.calls, [])

    def test_api_error_is_exit_4(self) -> None:
        fake = FakeGitHub()
        fake.fail_status = 500
        code, _, err, _ = _apply(fake=fake)
        self.assertEqual(code, EXIT_API)
        self.assertIn("500", err)

    def test_forbidden_product_repo_does_not_write(self) -> None:
        code, _, err, fake = _apply(repo="First-Light-TechHK/LearningGuidePortal")
        self.assertEqual(code, EXIT_CONFIG)
        self.assertIn("refusing", err)
        self.assertEqual(fake.calls, [])

    def test_apply_does_not_create_policy_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            before = set(p.name for p in cwd.iterdir())
            code, _, err, _ = _apply(dry_run=True, environ={})
            self.assertEqual(code, EXIT_OK, err)
            after = set(p.name for p in cwd.iterdir())
            self.assertEqual(before, after)
            self.assertFalse((cwd / "AGENTS.md").exists())
            self.assertFalse((cwd / ".github" / "CODEOWNERS").exists())


if __name__ == "__main__":
    unittest.main()
