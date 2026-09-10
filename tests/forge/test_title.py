"""PR title linter: fake titles only. No GitHub write."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from forge import EXIT_OK
from forge.__main__ import main
from forge.title import (
    ACTORS,
    EXAMPLE,
    PRODUCTS,
    TITLE_PATTERN,
    TITLE_RE,
    TYPES,
    EXIT_TITLE,
    lint_title,
    run_pr_title,
)

ROOT = Path(__file__).resolve().parents[2]


def _parts(title: str):
    code, message, parts = lint_title(title)
    return code, message, parts


class GoodTitlesTests(unittest.TestCase):
    def test_conventional_plus_actor_passes(self) -> None:
        goods = (
            "feat(overlay/dev): add cover triad and invariants",
            "fix(forge/admin): list pr-title in required_checks",
            "docs(docs/agent): explain Conventional Commit titles",
            "ci(ci/dev): add pr-title workflow",
            "test(forge/agent): cover title linter",
            "chore(docs/admin): tidy sop index",
            "refactor(overlay/dev): split select from run",
            "perf(forge/dev): cache ruleset template",
            "style(docs/dev): wrap pr-brief tables",
            "build(ci/admin): pin python 3.12",
            "revert(overlay/agent): undo generate hook",
            "feat(overlay/dev)!: rename inbox field",
        )
        for title in goods:
            with self.subTest(title=title):
                code, message, parts = _parts(title)
                self.assertEqual(code, EXIT_OK, message)
                self.assertEqual(message, "")
                self.assertIsNotNone(parts)
                self.assertIn(parts.type, TYPES)
                self.assertIn(parts.product, PRODUCTS)
                self.assertIn(parts.actor, ACTORS)

    def test_example_from_spec_passes(self) -> None:
        code, message, parts = _parts(EXAMPLE)
        self.assertEqual(code, EXIT_OK, message)
        self.assertEqual(parts.type, "feat")
        self.assertEqual(parts.product, "overlay")
        self.assertEqual(parts.actor, "dev")
        self.assertFalse(parts.breaking)


class BadTitlesTests(unittest.TestCase):
    def test_empty_fails(self) -> None:
        for title in ("", "   ", None, "\n", "\t"):
            with self.subTest(title=title):
                code, message, parts = _parts(title)
                self.assertEqual(code, EXIT_TITLE)
                self.assertIsNone(parts)
                self.assertTrue(message)

    def test_missing_type_fails(self) -> None:
        code, message, parts = _parts("add overlay cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIsNone(parts)
        self.assertIn("Conventional Commits", message)

    def test_missing_scope_fails(self) -> None:
        code, message, parts = _parts("feat: add overlay cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIsNone(parts)
        self.assertIn("scope", message)

    def test_missing_actor_fails(self) -> None:
        code, message, parts = _parts("feat(overlay): add cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIsNone(parts)
        self.assertIn("product/actor", message)

    def test_missing_product_fails(self) -> None:
        code, message, parts = _parts("feat(dev): add cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIsNone(parts)
        self.assertIn("product/actor", message)

    def test_unknown_type_fails(self) -> None:
        code, message, parts = _parts("feet(overlay/dev): add cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("type", message.lower())

    def test_uppercase_type_fails(self) -> None:
        code, message, parts = _parts("Feat(overlay/dev): add cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("lowercase", message)

    def test_unknown_product_fails(self) -> None:
        code, message, parts = _parts("feat(portal/dev): add cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("product", message)

    def test_unknown_actor_fails(self) -> None:
        code, message, parts = _parts("feat(overlay/intern): add cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("actor", message)

    def test_empty_subject_fails(self) -> None:
        for title in ("feat(overlay/dev):", "feat(overlay/dev):   "):
            with self.subTest(title=title):
                code, message, parts = _parts(title)
                self.assertEqual(code, EXIT_TITLE)
                self.assertIsNone(parts)

    def test_private_bracket_language_fails(self) -> None:
        code, message, parts = _parts("[开发][Overlay] add cover triad")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("Conventional Commits", message)
        self.assertNotIn("[开发]", EXAMPLE)

    def test_leading_actor_token_is_not_conventional(self) -> None:
        code, message, parts = _parts("dev feat(overlay): add cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("Conventional Commits", message)

    def test_missing_space_after_colon_fails(self) -> None:
        code, _, parts = _parts("feat(overlay/dev):add cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIsNone(parts)

    def test_mixed_product_scope_fails(self) -> None:
        code, _, parts = _parts("feat(overlay+docs/dev): add cover")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIsNone(parts)

    def test_newline_fails(self) -> None:
        code, message, parts = _parts("feat(overlay/dev): add cover\nsecond")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("single line", message)
        self.assertIsNone(parts)


class RegexLockTests(unittest.TestCase):
    def test_published_pattern_is_the_program_lock(self) -> None:
        self.assertEqual(TITLE_RE.pattern, TITLE_PATTERN)
        self.assertIsNotNone(TITLE_RE.fullmatch(EXAMPLE))
        self.assertIsNone(TITLE_RE.fullmatch("feat(overlay): missing actor"))
        self.assertIsNone(TITLE_RE.fullmatch(""))


class CliTests(unittest.TestCase):
    def test_pr_title_good_exits_0(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["pr-title", "--title", EXAMPLE],
            stdout=stdout,
            stderr=stderr,
            environ={},
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_title_alias_and_env(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["title"],
            stdout=stdout,
            stderr=stderr,
            environ={"PR_TITLE": EXAMPLE},
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())

    def test_bad_title_exits_2(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["pr-title", "--title", ""],
            stdout=stdout,
            stderr=stderr,
            environ={},
        )
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("empty", stderr.getvalue())

    def test_run_pr_title_does_not_need_github(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_pr_title(title="not conventional", environ={}, stdout=stdout, stderr=stderr)
        self.assertEqual(code, EXIT_TITLE)
        self.assertTrue(stderr.getvalue())


class WorkshopConfigTests(unittest.TestCase):
    def test_forge_yaml_lists_pr_title_check(self) -> None:
        text = (ROOT / "forge.yaml").read_text(encoding="utf-8")
        self.assertIn("overlay-check", text)
        self.assertIn("pr-title", text)
        self.assertIn("forge-check", text)
        self.assertIn("sop-lock", text)

    def test_pr_title_workflow_is_pull_request_only(self) -> None:
        text = (ROOT / ".github" / "workflows" / "pr-title.yml").read_text(encoding="utf-8")
        self.assertIn("name: pr-title", text)
        self.assertIn("pull_request", text)
        self.assertNotIn("\n  push:\n", text)
        self.assertIn("python -m forge pr-title", text)
        self.assertIn("pip install -r requirements.txt", text)
        overlay = (ROOT / ".github" / "workflows" / "overlay-check.yml").read_text(encoding="utf-8")
        self.assertNotIn("python -m forge pr-title", overlay)
        self.assertIn("forge ci-select", overlay)


if __name__ == "__main__":
    unittest.main()
