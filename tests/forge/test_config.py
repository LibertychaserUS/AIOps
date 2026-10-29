"""forge.yaml v1.1 schema: per-branch rules, title.scopes, docs_sync, unknown keys."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forge.apply import ForgeError, load_config, validate_config

from forge import EXIT_CONFIG, SCHEMA_ID


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


class PerFieldFallbackTests(unittest.TestCase):
    """ADR 0004 修订 (2026-10-29): a key absent in branches.<name> takes the legacy
    top-level value, else the default. Pinned so it cannot drift unnoticed."""

    def test_partial_branch_rule_inherits_legacy_fields(self) -> None:
        config = validate_config(
            {
                "schema": SCHEMA_ID,
                "protect": ["main"],
                "required_checks": ["unit", "lint"],
                "review": {"min_approvals": 2, "code_owners": False},
                "branches": {"main": {"code_owners": True}},
            }
        )
        main = config.rule_for("main")
        self.assertEqual(main.required_checks, ["unit", "lint"])
        self.assertEqual(main.approvals, 2)
        self.assertIs(main.code_owners, True)
        self.assertIsNone(main.promote_from)

    def test_partial_branch_rule_without_legacy_uses_defaults(self) -> None:
        config = validate_config(
            {
                "schema": SCHEMA_ID,
                "protect": ["main"],
                "branches": {"main": {"required_checks": ["unit"]}},
            }
        )
        main = config.rule_for("main")
        self.assertEqual(main.required_checks, ["unit"])
        self.assertEqual(main.approvals, 1)
        self.assertIs(main.code_owners, False)


class TitleScopeShapeTests(unittest.TestCase):
    def test_adopter_scope_outside_builtin_sets_is_accepted(self) -> None:
        config = validate_config(
            {"schema": SCHEMA_ID, "title": {"scopes": ["infra/dev", "web-app/qa2"]}}
        )
        self.assertEqual(config.title_scopes, ["infra/dev", "web-app/qa2"])

    def test_malformed_scope_entry_is_red_and_named(self) -> None:
        for bad in ("Infra/dev", "infra", "a/b/c", "infra/", "/dev", "1a/dev", "infra/Dev"):
            with self.subTest(bad=bad), self.assertRaises(ForgeError) as ctx:
                validate_config({"schema": SCHEMA_ID, "title": {"scopes": ["overlay/dev", bad]}})
            self.assertEqual(ctx.exception.code, EXIT_CONFIG)
            self.assertIn("illegal title.scopes item", ctx.exception.message)
            self.assertIn(repr(bad), ctx.exception.message)


class YamlParserTests(unittest.TestCase):
    """forge.yaml is read by PyYAML (safe loader, strict keys), not a hand-rolled subset."""

    def _load(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forge.yaml"
            path.write_text(text, encoding="utf-8")
            return load_config(path)

    def _red(self, text: str, needle: str) -> None:
        with self.assertRaises(ForgeError) as ctx:
            self._load(text)
        self.assertEqual(ctx.exception.code, EXIT_CONFIG)
        self.assertIn(needle, ctx.exception.message)

    def test_unquoted_url_is_a_string_not_a_mapping(self) -> None:
        config = self._load(
            "schema: forge-config/v1\nforbidden_live_repos:\n  - https://github.com/Acme/Prod.git\n"
        )
        self.assertEqual(config.forbidden_live_repos, ["acme/prod"])

    def test_list_item_with_colon_is_a_string(self) -> None:
        config = self._load("schema: forge-config/v1\nrequired_checks:\n  - a:b\n")
        # `- a:b` (no space) is a plain scalar; only `- c: d` opens a mapping.
        self.assertEqual(config.required_checks, ["a:b"])

    def test_colon_space_item_is_a_mapping_and_red_as_check_name(self) -> None:
        self._red("schema: forge-config/v1\nrequired_checks:\n  - c: d\n", "illegal required_checks item")

    def test_flow_and_block_styles_agree(self) -> None:
        block = self._load("schema: forge-config/v1\nprotect:\n  - dev\n  - main\n")
        flow = self._load("schema: forge-config/v1\nprotect: [dev, main]\n")
        self.assertEqual(block.protect, flow.protect)

    def test_numeric_looking_names_stay_strings(self) -> None:
        config = self._load(
            "schema: forge-config/v1\nprotect:\n  - 1.0\n  - 2026-01-01\n  - 1e3\n"
            "tag_patterns:\n  - 1.10\n"
        )
        self.assertEqual(config.protect, ["1.0", "2026-01-01", "1e3"])
        self.assertEqual(config.tag_patterns, ["1.10"])

    def test_yaml11_words_are_not_booleans(self) -> None:
        # yes / no / on / off were never accepted by forge-config/v1; keep it so.
        self._red("schema: forge-config/v1\nreview:\n  code_owners: yes\n", "illegal review.code_owners: 'yes'")
        self._red("schema: forge-config/v1\nreview:\n  code_owners: on\n", "illegal review.code_owners: 'on'")
        config = self._load("schema: forge-config/v1\nreview:\n  code_owners: true\n  min_approvals: 2\n")
        self.assertIs(config.code_owners, True)
        self.assertEqual(config.min_approvals, 2)

    def test_empty_and_comment_only_documents_are_red(self) -> None:
        self._red("", "empty document")
        self._red("# nothing here\n", "empty document")

    def test_non_mapping_document_is_red(self) -> None:
        self._red("- a\n- b\n", "document must be a mapping")

    def test_duplicate_keys_at_every_level_are_red(self) -> None:
        self._red("schema: forge-config/v1\nprotect: [a]\nprotect: [b]\n", "duplicate key protect")
        self._red(
            "schema: forge-config/v1\nreview:\n  min_approvals: 1\n  min_approvals: 2\n",
            "line 4: duplicate key min_approvals",
        )
        self._red(
            "schema: forge-config/v1\nprotect: [main]\nbranches:\n  main:\n    approvals: 1\n    approvals: 2\n",
            "duplicate key approvals",
        )
        self._red(
            "schema: forge-config/v1\ndocs_sync:\n  - {paths: [a/], paths: [b/], require: [X.md]}\n",
            "duplicate key paths",
        )

    def test_syntax_error_is_a_one_line_config_error(self) -> None:
        with self.assertRaises(ForgeError) as ctx:
            self._load("schema: forge-config/v1\nprotect: [main\n")
        self.assertEqual(ctx.exception.code, EXIT_CONFIG)
        self.assertTrue(ctx.exception.message.startswith("illegal forge.yaml: "))
        self.assertNotIn("\n", ctx.exception.message)

    def test_unknown_key_message_survives_parser_swap(self) -> None:
        self._red("schema: forge-config/v1\ndeny_path: [x]\n", "did you mean deny_paths")

    def test_workshop_forge_yaml_round_trips(self) -> None:
        config = load_config(Path(__file__).resolve().parents[2] / "forge.yaml")
        self.assertEqual(config.protect, ["dev", "main"])
        self.assertIn("ci/agent", config.title_scopes)


class StrictNestedKeyTests(unittest.TestCase):
    def _red(self, raw: dict, needle: str) -> None:
        with self.assertRaises(ForgeError) as ctx:
            validate_config({"schema": SCHEMA_ID, **raw})
        self.assertEqual(ctx.exception.code, EXIT_CONFIG)
        self.assertIn(needle, ctx.exception.message)

    def test_branch_key_typo_is_red_with_suggestion(self) -> None:
        self._red(
            {"protect": ["main"], "branches": {"main": {"aprovals": 2}}},
            "did you mean branches.main.approvals",
        )
        self._red(
            {"protect": ["main"], "branches": {"main": {"code_owner": True}}},
            "did you mean branches.main.code_owners",
        )

    def test_review_key_typo_is_red_with_suggestion(self) -> None:
        self._red({"review": {"min_approval": 3}}, "did you mean review.min_approvals")
        self._red({"review": {"codeowners": True}}, "review.codeowners")

    def test_branch_not_in_protect_is_red(self) -> None:
        self._red(
            {"protect": ["main"], "branches": {"release": {"approvals": 2}}},
            "not in protect",
        )

    def test_promote_from_not_in_protect_is_red(self) -> None:
        self._red(
            {"protect": ["main"], "branches": {"main": {"promote_from": "dev"}}},
            "promote_from",
        )

    def test_forbidden_repo_entries_are_normalised(self) -> None:
        config = validate_config(
            {
                "schema": SCHEMA_ID,
                "forbidden_live_repos": [
                    "https://github.com/Acme/Prod.git",
                    "github.com/acme/two/",
                    "Acme/Three",
                ],
            }
        )
        self.assertEqual(config.forbidden_live_repos, ["acme/prod", "acme/two", "acme/three"])

    def test_forbidden_repo_entry_not_owner_name_is_red(self) -> None:
        self._red({"forbidden_live_repos": ["https://gitlab.com/a/b"]}, "forbidden_live_repos")
        self._red({"forbidden_live_repos": ["acme"]}, "forbidden_live_repos")


if __name__ == "__main__":
    unittest.main()
