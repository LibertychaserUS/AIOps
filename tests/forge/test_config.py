"""forge.yaml v1.1 schema: per-branch rules, title.scopes, docs_sync, unknown keys."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forge import EXIT_CONFIG, SCHEMA_ID
from forge.apply import ForgeError, load_config, validate_config


class LegacyConfigTests(unittest.TestCase):
    def test_legacy_required_checks_and_review_still_accepted(self) -> None:
        config = validate_config(
            {
                "schema": SCHEMA_ID,
                "protect": ["main"],
                "required_checks": ["unit", "lint"],
                "review": {"min_approvals": 1, "code_owners": True},
            }
        )
        self.assertEqual(config.protect, ["main"])
        self.assertEqual(config.required_checks, ["unit", "lint"])
        self.assertEqual(config.min_approvals, 1)
        self.assertIs(config.code_owners, True)
        rule = config.rule_for("main")
        self.assertEqual(rule.required_checks, ["unit", "lint"])
        self.assertEqual(rule.approvals, 1)
        self.assertIs(rule.code_owners, True)

    def test_missing_fields_use_defaults(self) -> None:
        config = validate_config({"schema": SCHEMA_ID})
        self.assertEqual(config.protect, ["main"])
        self.assertEqual(config.forbidden_live_repos, [])
        self.assertEqual(config.tag_patterns, ["overlay-v*", "forge-v*"])
        self.assertIsNone(config.title_scopes)
        self.assertEqual(config.docs_sync, [])


class BranchRulesTests(unittest.TestCase):
    def test_branches_override_legacy_top_level(self) -> None:
        config = validate_config(
            {
                "schema": SCHEMA_ID,
                "protect": ["dev", "main"],
                "required_checks": ["legacy"],
                "review": {"min_approvals": 9, "code_owners": False},
                "branches": {
                    "dev": {
                        "required_checks": ["unit", "lint"],
                        "approvals": 0,
                        "code_owners": False,
                    },
                    "main": {
                        "required_checks": ["unit", "lint", "forge-check"],
                        "approvals": 1,
                        "code_owners": True,
                        "promote_from": "dev",
                    },
                },
            }
        )
        self.assertEqual(config.protect, ["dev", "main"])
        dev = config.rule_for("dev")
        self.assertEqual(dev.required_checks, ["unit", "lint"])
        self.assertEqual(dev.approvals, 0)
        self.assertIs(dev.code_owners, False)
        main = config.rule_for("main")
        self.assertEqual(main.required_checks, ["unit", "lint", "forge-check"])
        self.assertEqual(main.approvals, 1)
        self.assertIs(main.code_owners, True)
        self.assertEqual(main.promote_from, "dev")

    def test_title_scopes_any_and_list(self) -> None:
        any_cfg = validate_config({"schema": SCHEMA_ID, "title": {"scopes": "any"}})
        self.assertEqual(any_cfg.title_scopes, "any")
        listed = validate_config(
            {
                "schema": SCHEMA_ID,
                "title": {"scopes": ["overlay/agent", "forge/agent"]},
            }
        )
        self.assertEqual(listed.title_scopes, ["overlay/agent", "forge/agent"])

    def test_docs_sync_table(self) -> None:
        config = validate_config(
            {
                "schema": SCHEMA_ID,
                "docs_sync": [
                    {"paths": ["forge/**"], "require": ["CHANGELOG.md", "docs/cli.md"]},
                    {"paths": ["overlay/**"], "require": ["CHANGELOG.md"]},
                ],
            }
        )
        self.assertEqual(len(config.docs_sync), 2)
        self.assertEqual(config.docs_sync[0].paths, ["forge/**"])
        self.assertEqual(config.docs_sync[0].require, ["CHANGELOG.md", "docs/cli.md"])

    def test_forbidden_live_repos_default_empty(self) -> None:
        config = validate_config({"schema": SCHEMA_ID})
        self.assertEqual(config.forbidden_live_repos, [])
        listed = validate_config(
            {
                "schema": SCHEMA_ID,
                "forbidden_live_repos": ["first-light-techhk/learningguideportal"],
            }
        )
        self.assertEqual(
            listed.forbidden_live_repos, ["first-light-techhk/learningguideportal"]
        )


class UnknownKeyTests(unittest.TestCase):
    def test_unknown_top_level_key_is_red_with_did_you_mean(self) -> None:
        with self.assertRaises(ForgeError) as ctx:
            validate_config({"schema": SCHEMA_ID, "deny_path": [".github/"]})
        self.assertEqual(ctx.exception.code, EXIT_CONFIG)
        self.assertIn("unknown key deny_path", ctx.exception.message)
        self.assertIn("did you mean deny_paths", ctx.exception.message)

    def test_unknown_key_without_close_match_still_red(self) -> None:
        with self.assertRaises(ForgeError) as ctx:
            validate_config({"schema": SCHEMA_ID, "zzzznotakey": 1})
        self.assertEqual(ctx.exception.code, EXIT_CONFIG)
        self.assertIn("unknown key zzzznotakey", ctx.exception.message)

    def test_load_config_rejects_unknown_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forge.yaml"
            path.write_text(
                "schema: forge-config/v1\ndeny_path:\n  - .github/\n",
                encoding="utf-8",
            )
            with self.assertRaises(ForgeError) as ctx:
                load_config(path)
            self.assertIn("did you mean deny_paths", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
