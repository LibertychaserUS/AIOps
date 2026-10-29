"""PR title linter: fake titles only. No GitHub write."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from forge.__main__ import main
from forge.title import (
    ACTORS,
    EXAMPLE,
    EXIT_TITLE,
    PRODUCTS,
    TITLE_PATTERN,
    TITLE_RE,
    TYPES,
    head_commit_subject,
    head_is_merge,
    lint_title,
    optional_text,
    resolve_arg_or_env,
    resolve_spec_body,
    resolve_spec_title,
    run_pr_title,
)

from forge import EXIT_OK

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


class ScopeModeTests(unittest.TestCase):
    def test_scopes_any_allows_missing_scope(self) -> None:
        code, message, parts = lint_title("feat: add cover triad", scopes="any")
        self.assertEqual(code, EXIT_OK, message)
        self.assertIsNotNone(parts)

    def test_scopes_any_rejects_trailing_period_and_long_title(self) -> None:
        code, message, _ = lint_title("feat: add a period.", scopes="any")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("period", message)
        long_title = "feat: " + ("a" * 70)
        self.assertGreater(len(long_title), 72)
        code, message, _ = lint_title(long_title, scopes="any")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("72", message)

    def test_scopes_list_keeps_product_actor_and_membership(self) -> None:
        allowed = ["overlay/agent", "forge/agent"]
        code, message, _ = lint_title("feat(overlay/agent): add cover", scopes=allowed)
        self.assertEqual(code, EXIT_OK, message)
        code, message, _ = lint_title("feat(overlay/dev): add cover", scopes=allowed)
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("title.scopes", message)
        code, message, _ = lint_title("feat: add cover", scopes=allowed)
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("scope", message)


class UnifiedGrammarTests(unittest.TestCase):
    """Length, trailing period and visible subject hold in every scopes mode."""

    MODES = (None, "any", ["overlay/dev", "infra/dev", "ci/agent"])

    def test_header_over_72_fails_in_every_mode(self) -> None:
        title = "feat(overlay/dev): " + "a" * 60
        self.assertGreater(len(title), 72)
        for scopes in self.MODES:
            with self.subTest(scopes=scopes):
                code, message, _ = lint_title(title, scopes=scopes)
                self.assertEqual(code, EXIT_TITLE)
                self.assertIn("72", message)
        exactly = "feat(overlay/dev): " + "a" * (72 - len("feat(overlay/dev): "))
        self.assertEqual(len(exactly), 72)
        for scopes in self.MODES:
            self.assertEqual(lint_title(exactly, scopes=scopes)[0], EXIT_OK)

    def test_trailing_period_fails_in_every_mode(self) -> None:
        for scopes in self.MODES:
            for title in ("feat(overlay/dev): add cover.", "feat(overlay/dev): 加封面。"):
                with self.subTest(scopes=scopes, title=title):
                    code, message, _ = lint_title(title, scopes=scopes)
                    self.assertEqual(code, EXIT_TITLE)
                    self.assertIn("period", message)

    def test_invisible_subject_fails_in_every_mode(self) -> None:
        for scopes in self.MODES:
            for ch in ("\u200b", "\u200c", "\u200d", "\ufeff", "\u200b \ufeff"):
                with self.subTest(scopes=scopes, ch=ch):
                    code, message, parts = lint_title(f"feat(overlay/dev): {ch}", scopes=scopes)
                    self.assertEqual(code, EXIT_TITLE)
                    self.assertIsNone(parts)
                    self.assertIn("subject", message)

    def test_line_separators_are_not_single_line(self) -> None:
        for ch in ("\u2028", "\u2029"):
            code, message, _ = lint_title(f"feat(overlay/dev): a{ch}b")
            self.assertEqual(code, EXIT_TITLE)
            self.assertIn("single line", message)

    def test_adopter_scope_passes_when_listed(self) -> None:
        code, message, parts = lint_title("feat(infra/dev): add runner", scopes=["infra/dev"])
        self.assertEqual(code, EXIT_OK, message)
        self.assertEqual((parts.product, parts.actor), ("infra", "dev"))
        code, message, _ = lint_title("feat(infra/dev): add runner", scopes=["overlay/dev"])
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("title.scopes", message)
        code, message, _ = lint_title("feat(infra/dev): add runner")
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("product", message)

    def test_workshop_promote_title_passes_workshop_scopes(self) -> None:
        from forge.apply import load_config
        from forge.promote import promote_title

        scopes = load_config(ROOT / "forge.yaml").title_scopes
        title = promote_title("dev", "main", "0123abcd", scopes)
        self.assertTrue(title.startswith("chore(ci/agent): "))
        code, message, _ = lint_title(title, scopes=scopes)
        self.assertEqual(code, EXIT_OK, message)


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

    def test_push_blank_env_lints_head_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "event.json"
            event.write_text(
                json.dumps({"head_commit": {"message": f"{EXAMPLE}\n\nbody"}}),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = main(
                ["pr-title", "--root", tmp],
                stdout=stdout,
                stderr=stderr,
                environ={
                    "PR_TITLE": "",
                    "PR_BODY": "",
                    "GITHUB_EVENT_NAME": "push",
                    "GITHUB_EVENT_PATH": str(event),
                },
            )
            self.assertEqual(code, EXIT_OK, stderr.getvalue())

    def test_pull_request_blank_env_fails(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["pr-title", "--root", str(ROOT)],
            stdout=stdout,
            stderr=stderr,
            environ={"PR_TITLE": "", "GITHUB_EVENT_NAME": "pull_request"},
        )
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("empty", stderr.getvalue())

    def test_pull_request_unset_title_fails(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["pr-title", "--root", str(ROOT)],
            stdout=stdout,
            stderr=stderr,
            environ={"GITHUB_EVENT_NAME": "pull_request"},
        )
        self.assertEqual(code, EXIT_TITLE)
        self.assertIn("empty", stderr.getvalue())

    def test_run_pr_title_does_not_need_github(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_pr_title(title="not conventional", environ={}, stdout=stdout, stderr=stderr)
        self.assertEqual(code, EXIT_TITLE)
        self.assertTrue(stderr.getvalue())


class OptionalEnvTextTests(unittest.TestCase):
    def test_blank_env_is_omitted(self) -> None:
        self.assertIsNone(optional_text(None))
        self.assertIsNone(optional_text(""))
        self.assertIsNone(optional_text("  \n"))
        self.assertEqual(optional_text(EXAMPLE), EXAMPLE)

    def test_explicit_empty_arg_is_kept(self) -> None:
        self.assertEqual(resolve_arg_or_env("", {"PR_TITLE": EXAMPLE}, "PR_TITLE"), "")
        self.assertIsNone(resolve_arg_or_env(None, {"PR_TITLE": ""}, "PR_TITLE"))
        self.assertEqual(resolve_arg_or_env(None, {"PR_TITLE": EXAMPLE}, "PR_TITLE"), EXAMPLE)


class SpecEventStateTests(unittest.TestCase):
    """Event × env × source — the states the old fixtures missed."""

    def test_resolve_matrix(self) -> None:
        cases = [
            (EXAMPLE, {}, "arg", EXAMPLE),
            ("", {"PR_TITLE": EXAMPLE, "GITHUB_EVENT_NAME": "push"}, "arg", ""),
            (None, {"PR_TITLE": EXAMPLE, "GITHUB_EVENT_NAME": "pull_request"}, "env", EXAMPLE),
            (None, {"PR_TITLE": "", "GITHUB_EVENT_NAME": "pull_request"}, "env", ""),
            (None, {"GITHUB_EVENT_NAME": "pull_request"}, "env", ""),
            (None, {}, "omitted", None),
        ]
        for explicit, environ, source, text in cases:
            with self.subTest(explicit=explicit, environ=environ):
                spec = resolve_spec_title(explicit, environ, root=ROOT)
                self.assertEqual(spec.source, source)
                self.assertEqual(spec.text, text)

    def test_actions_empty_title_without_event_name_uses_commit(self) -> None:
        spec = resolve_spec_title(None, {"PR_TITLE": ""}, root=ROOT)
        self.assertEqual(spec.source, "commit")
        self.assertTrue(spec.text)

    def test_push_without_commit_is_empty_not_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = resolve_spec_title(
                None,
                {"PR_TITLE": "", "GITHUB_EVENT_NAME": "push"},
                root=tmp,
            )
            self.assertEqual(spec.source, "env")
            self.assertEqual(spec.text, "")
            stderr = io.StringIO()
            code = run_pr_title(
                title=None,
                environ={"PR_TITLE": "", "GITHUB_EVENT_NAME": "push"},
                stdout=io.StringIO(),
                stderr=stderr,
                root=tmp,
            )
            self.assertEqual(code, EXIT_TITLE)
            self.assertIn("empty", stderr.getvalue())

    def test_body_matrix(self) -> None:
        brief = "## 做了什么\n"
        cases = [
            (brief, {}, "arg", brief),
            (None, {"PR_BODY": brief, "GITHUB_EVENT_NAME": "pull_request"}, "env", brief),
            (None, {"PR_BODY": "", "GITHUB_EVENT_NAME": "pull_request"}, "env", ""),
            (None, {"GITHUB_EVENT_NAME": "pull_request"}, "env", ""),
            (None, {"PR_BODY": "", "GITHUB_EVENT_NAME": "push"}, "omitted", None),
            (None, {}, "omitted", None),
        ]
        for explicit, environ, source, text in cases:
            with self.subTest(explicit=explicit, environ=environ):
                spec = resolve_spec_body(explicit, environ)
                self.assertEqual(spec.source, source)
                self.assertEqual(spec.text, text)

    def test_push_reads_event_head_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "event.json"
            event.write_text(
                json.dumps({"head_commit": {"message": f"{EXAMPLE}\n\nbody"}}),
                encoding="utf-8",
            )
            spec = resolve_spec_title(
                None,
                {
                    "PR_TITLE": "",
                    "GITHUB_EVENT_NAME": "push",
                    "GITHUB_EVENT_PATH": str(event),
                },
                root=tmp,
            )
            self.assertEqual(spec.source, "commit")
            self.assertEqual(spec.text, EXAMPLE)

    def test_push_bad_commit_subject_fails_lint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "event.json"
            event.write_text(
                json.dumps({"head_commit": {"message": "wip\n"}}),
                encoding="utf-8",
            )
            stderr = io.StringIO()
            code = run_pr_title(
                title=None,
                environ={
                    "PR_TITLE": "",
                    "GITHUB_EVENT_NAME": "push",
                    "GITHUB_EVENT_PATH": str(event),
                },
                stdout=io.StringIO(),
                stderr=stderr,
                root=tmp,
            )
            self.assertEqual(code, EXIT_TITLE)
            self.assertTrue(stderr.getvalue())

    def test_whitespace_pr_title_on_pull_request_is_empty(self) -> None:
        spec = resolve_spec_title(
            None,
            {"PR_TITLE": "  \n", "GITHUB_EVENT_NAME": "pull_request"},
            root=ROOT,
        )
        self.assertEqual(spec.source, "env")
        self.assertEqual(spec.text, "")


class WorkshopConfigTests(unittest.TestCase):
    def test_forge_yaml_lists_pr_title_check(self) -> None:
        text = (ROOT / "forge.yaml").read_text(encoding="utf-8")
        self.assertIn("overlay-check", text)
        self.assertIn("pr-title", text)
        self.assertIn("forge-check", text)
        self.assertIn("sop-lock", text)
        self.assertIn("unittest", text)

    def test_pr_title_workflow_is_pull_request_only(self) -> None:
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("name: pr-title", text)
        self.assertIn("if: github.event_name == 'pull_request'", text)
        self.assertIn("python -m forge pr-title", text)
        self.assertIn("pip install -r requirements.txt", text)
        overlay = (ROOT / ".github" / "workflows" / "overlay-check.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("forge ci-select", overlay)
        self.assertIn("python -m forge pr-title", overlay)
        self.assertIn("name: spec", overlay)
        self.assertIn("name: unittest", text)


if __name__ == "__main__":
    unittest.main()


class PushMergeCommitTests(unittest.TestCase):
    """A base-branch merge commit at HEAD is plumbing: push lints the agent's own commit."""

    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(root), "-c", "commit.gpgsign=false", *args],
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@example.com",
                "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.com",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
            },
        )

    def _repo_with_merge_head(self, tmp: str, feature_subject: str) -> Path:
        root = Path(tmp)
        self._git(root, "init", "-q", "-b", "dev")
        (root / "a.txt").write_text("a\n", encoding="utf-8")
        self._git(root, "add", "a.txt")
        self._git(root, "commit", "-q", "-m", "chore(ci/dev): base")
        self._git(root, "checkout", "-q", "-b", "agent/x")
        (root / "b.txt").write_text("b\n", encoding="utf-8")
        self._git(root, "add", "b.txt")
        self._git(root, "commit", "-q", "-m", feature_subject)
        self._git(root, "checkout", "-q", "dev")
        (root / "c.txt").write_text("c\n", encoding="utf-8")
        self._git(root, "add", "c.txt")
        self._git(root, "commit", "-q", "-m", "fix(ci/dev): base moves")
        self._git(root, "checkout", "-q", "agent/x")
        self._git(root, "merge", "-q", "--no-ff", "-m", "Merge branch 'dev' into agent/x", "dev")
        return root

    def test_merge_head_lints_first_parent_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo_with_merge_head(tmp, EXAMPLE)
            self.assertTrue(head_is_merge(root))
            self.assertEqual(head_commit_subject(root, {}), EXAMPLE)
            code = main(
                ["pr-title", "--root", str(root)],
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                environ={"PR_TITLE": "", "GITHUB_EVENT_NAME": "push"},
            )
            self.assertEqual(code, EXIT_OK)

    def test_merge_head_does_not_hide_bad_feature_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo_with_merge_head(tmp, "wip")
            stderr = io.StringIO()
            code = main(
                ["pr-title", "--root", str(root)],
                stdout=io.StringIO(),
                stderr=stderr,
                environ={"PR_TITLE": "", "GITHUB_EVENT_NAME": "push"},
            )
            self.assertEqual(code, EXIT_TITLE, stderr.getvalue())

    def test_plain_head_is_not_merge(self) -> None:
        self.assertFalse(head_is_merge(None))
