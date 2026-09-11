"""Forge apply against a fake Rulesets API. Never talks to a real repo."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from forge import COPY_FILES_NOTE, EXIT_API, EXIT_AUTH, EXIT_CONFIG, EXIT_OK, TAG_RULESET_NAME, branch_ruleset_name
from forge.apply import (
    build_branch_payload,
    build_payloads,
    load_config,
    load_ruleset_template,
    run_apply,
    validate_config,
)
from forge.__main__ import main

from tests.forge.fake_github import FakeGitHub

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "forge" / "forge.example.yaml"
LG_EXAMPLE = ROOT / "examples" / "learning-guide" / "forge.yaml"
FAKE_API = "https://forge.test"
REPO = "acme/widget"
SIMPLE_YAML = (
    "schema: forge-config/v1\n"
    "protect:\n"
    "  - main\n"
    "required_checks:\n"
    "  - unit\n"
    "review:\n"
    "  min_approvals: 1\n"
    "  code_owners: false\n"
)


def _write_simple(tmp: str) -> Path:
    path = Path(tmp) / "forge.yaml"
    path.write_text(SIMPLE_YAML, encoding="utf-8")
    return path


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
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_simple(tmp)
            fake = FakeGitHub()
            first, out1, err1, _ = _apply(fake=fake, path=path)
            self.assertEqual(first, EXIT_OK, err1)
            # main branch + tags
            self.assertEqual(fake.methods().count("POST"), 2)
            self.assertEqual(fake.methods().count("PUT"), 0)
            self.assertIn("created ruleset", out1)
            self.assertIn(branch_ruleset_name("main"), out1)
            self.assertIn(TAG_RULESET_NAME, out1)
            self.assertIn("protect: main", out1)
            self.assertIn(COPY_FILES_NOTE.splitlines()[0], out1)

            second, out2, err2, _ = _apply(fake=fake, path=path)
            self.assertEqual(second, EXIT_OK, err2)
            self.assertEqual(fake.methods().count("POST"), 2)
            self.assertEqual(fake.methods().count("PUT"), 2)
            self.assertIn("updated ruleset", out2)
            names = {item["name"] for item in fake.rulesets}
            self.assertEqual(names, {branch_ruleset_name("main"), TAG_RULESET_NAME})

    def test_existing_same_name_puts_without_post(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_simple(tmp)
            fake = FakeGitHub()
            fake.rulesets.append({"id": 9, "name": branch_ruleset_name("main")})
            fake.rulesets.append({"id": 10, "name": TAG_RULESET_NAME})
            fake.next_id = 11
            code, out, err, _ = _apply(fake=fake, path=path)
            self.assertEqual(code, EXIT_OK, err)
            self.assertEqual(fake.methods().count("POST"), 0)
            self.assertEqual(fake.methods().count("PUT"), 2)
            self.assertIn("updated ruleset id=9", out)
            self.assertIn("updated ruleset id=10", out)

    def test_other_ruleset_name_still_posts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_simple(tmp)
            fake = FakeGitHub()
            fake.rulesets.append({"id": 3, "name": "someone-else"})
            code, _, err, _ = _apply(fake=fake, path=path)
            self.assertEqual(code, EXIT_OK, err)
            self.assertEqual(fake.methods().count("POST"), 2)
            self.assertEqual(fake.methods().count("PUT"), 0)

    def test_per_protect_branch_gets_its_own_ruleset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forge.yaml"
            path.write_text(
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
                "    code_owners: true\n",
                encoding="utf-8",
            )
            fake = FakeGitHub()
            code, out, err, _ = _apply(fake=fake, path=path)
            self.assertEqual(code, EXIT_OK, err)
            names = [item["name"] for item in fake.rulesets]
            self.assertEqual(
                names,
                [branch_ruleset_name("dev"), branch_ruleset_name("main"), TAG_RULESET_NAME],
            )
            self.assertIn(branch_ruleset_name("dev"), out)
            self.assertIn(branch_ruleset_name("main"), out)
            self.assertEqual(fake.methods().count("POST"), 3)


class DefaultPayloadTests(unittest.TestCase):
    def test_default_json_template_has_pr_and_locks(self) -> None:
        template = load_ruleset_template()
        self.assertEqual(template["bypass_actors"], [])
        types = [rule["type"] for rule in template["rules"]]
        self.assertIn("deletion", types)
        self.assertIn("non_fast_forward", types)
        self.assertIn("pull_request", types)

        payload = build_branch_payload(validate_config({"schema": "forge-config/v1"}), "main")
        self.assertEqual(payload["name"], branch_ruleset_name("main"))
        self.assertEqual(payload["bypass_actors"], [])
        self.assertEqual(payload["conditions"]["ref_name"]["include"], ["refs/heads/main"])
        self.assertEqual(payload["conditions"]["ref_name"]["exclude"], [])
        pr = next(rule for rule in payload["rules"] if rule["type"] == "pull_request")
        self.assertEqual(pr["parameters"]["required_approving_review_count"], 1)
        self.assertIs(pr["parameters"]["require_code_owner_review"], False)
        self.assertIs(pr["parameters"]["dismiss_stale_reviews_on_push"], True)
        types = [rule["type"] for rule in payload["rules"]]
        self.assertIn("required_status_checks", types)
        check = next(rule for rule in payload["rules"] if rule["type"] == "required_status_checks")
        self.assertIs(check["parameters"]["strict_required_status_checks_policy"], True)
        self.assertEqual(check["parameters"]["required_status_checks"], [])

    def test_example_yaml_writes_required_status_checks(self) -> None:
        config = load_config(EXAMPLE)
        self.assertEqual(config.protect, ["dev", "main"])
        main = config.rule_for("main")
        self.assertEqual(main.approvals, 1)
        self.assertIs(main.code_owners, True)
        self.assertEqual(main.required_checks, ["unit", "lint", "overlay-check"])
        payload = build_branch_payload(config, "main")
        rule = next(
            item for item in payload["rules"] if item["type"] == "required_status_checks"
        )
        contexts = [item["context"] for item in rule["parameters"]["required_status_checks"]]
        self.assertEqual(contexts, ["unit", "lint", "overlay-check"])
        self.assertIs(rule["parameters"]["strict_required_status_checks_policy"], True)
        lg = load_config(LG_EXAMPLE)
        self.assertEqual(lg.protect, ["dev", "main"])
        self.assertIn(".github/workflows/", lg.deny_paths)
        self.assertEqual(lg.rule_for("main").promote_from, "dev")
        self.assertEqual(lg.rule_for("dev").approvals, 0)
        self.assertNotIn("Verify", lg.rule_for("main").required_checks)

    def test_workshop_yaml_writes_all_required_checks_per_branch(self) -> None:
        config = load_config(ROOT / "forge.yaml")
        payloads = {item["name"]: item for item in build_payloads(config)}
        for branch in config.protect:
            payload = payloads[branch_ruleset_name(branch)]
            rule = next(
                item for item in payload["rules"] if item["type"] == "required_status_checks"
            )
            contexts = [item["context"] for item in rule["parameters"]["required_status_checks"]]
            expected = config.rule_for(branch).required_checks
            self.assertEqual(contexts, expected)
            pr = next(item for item in payload["rules"] if item["type"] == "pull_request")
            self.assertEqual(pr["parameters"]["required_approving_review_count"], config.rule_for(branch).approvals)
            self.assertIs(
                pr["parameters"]["require_code_owner_review"], config.rule_for(branch).code_owners
            )
        tag = payloads[TAG_RULESET_NAME]
        self.assertEqual(tag["target"], "tag")
        types = [rule["type"] for rule in tag["rules"]]
        self.assertEqual(set(types), {"deletion", "non_fast_forward", "update"})
        includes = tag["conditions"]["ref_name"]["include"]
        self.assertIn("refs/tags/overlay-v*", includes)
        self.assertIn("refs/tags/forge-v*", includes)

    def test_missing_fields_use_defaults(self) -> None:
        config = validate_config({"schema": "forge-config/v1"})
        self.assertEqual(config.protect, ["main"])
        self.assertEqual(config.min_approvals, 1)
        self.assertIs(config.code_owners, False)
        self.assertEqual(config.agent_branch_prefixes, ["cursor/", "copilot/"])
        self.assertEqual(config.forbidden_live_repos, [])


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
    def test_dry_run_prints_all_payloads_and_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_simple(tmp)
            fake = FakeGitHub()
            code, out, err, _ = _apply(fake=fake, dry_run=True, environ={}, path=path)
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn("dry-run", out)
            payloads = json.loads(out.split("dry-run", 1)[1].split("protect:", 1)[0])
            self.assertIsInstance(payloads, list)
            names = [item["name"] for item in payloads]
            self.assertEqual(names, [branch_ruleset_name("main"), TAG_RULESET_NAME])
            self.assertIn("copy these files", out)
            self.assertEqual(fake.calls, [])
            self.assertEqual(fake.writes(), [])

    def test_missing_token_exits_2_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_simple(tmp)
            code, _, err, fake = _apply(environ={}, path=path)
            self.assertEqual(code, EXIT_AUTH)
            self.assertIn("missing", err)
            self.assertEqual(fake.calls, [])

    def test_cli_dry_run_does_not_call_write_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_simple(tmp)
            fake = FakeGitHub()
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = main(
                ["apply", "--repo", REPO, "--dry-run", "--path", str(path)],
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
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_simple(tmp)
            fake = FakeGitHub()
            fake.fail_status = 500
            code, _, err, _ = _apply(fake=fake, path=path)
            self.assertEqual(code, EXIT_API)
            self.assertIn("500", err)

    def test_forbidden_product_repo_from_yaml_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forge.yaml"
            path.write_text(
                SIMPLE_YAML + "forbidden_live_repos:\n  - first-light-techhk/learningguideportal\n",
                encoding="utf-8",
            )
            code, _, err, fake = _apply(
                repo="First-Light-TechHK/LearningGuidePortal",
                path=path,
            )
            self.assertEqual(code, EXIT_CONFIG)
            self.assertIn("refusing", err)
            self.assertEqual(fake.calls, [])

    def test_unlisted_fork_is_allowed_when_yaml_list_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_simple(tmp)
            code, _, err, fake = _apply(
                repo="LibertychaserUS/LearningGuidePortal",
                path=path,
                dry_run=True,
                environ={},
            )
            self.assertEqual(code, EXIT_OK, err)
            self.assertEqual(fake.calls, [])

    def test_ilovelearningguide_hostname_is_still_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_simple(tmp)
            code, _, err, fake = _apply(
                repo="acme/ilovelearningguide-mirror",
                path=path,
            )
            self.assertEqual(code, EXIT_CONFIG)
            self.assertIn("refusing", err)
            self.assertEqual(fake.calls, [])

    def test_apply_does_not_create_policy_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            before = set(p.name for p in cwd.iterdir())
            path = _write_simple(tmp)
            code, _, err, _ = _apply(dry_run=True, environ={}, path=path)
            self.assertEqual(code, EXIT_OK, err)
            after = set(p.name for p in cwd.iterdir())
            self.assertEqual(before | {"forge.yaml"}, after)
            self.assertFalse((cwd / "AGENTS.md").exists())
            self.assertFalse((cwd / ".github" / "CODEOWNERS").exists())


if __name__ == "__main__":
    unittest.main()
