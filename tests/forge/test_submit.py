"""Forge submit against a fake Pulls API. Never talks to a real repo. Never merges."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from forge import EXIT_AUTH, EXIT_CONFIG, EXIT_OK
from forge.__main__ import main
from forge.submit import BODY_HEADINGS, run_submit
from forge.title import EXAMPLE, lint_title

from tests.forge.fake_github import FakeGitHub

FAKE_API = "https://forge.test"
REPO = "acme/widget"
HEAD = "cursor/feature"
TITLE = "feat(forge/dev): add submit middleware"


class FakePush:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, remote: str, ref: str) -> None:
        self.calls.append((remote, ref))


def _submit(**kwargs):
    fake = kwargs.pop("fake", FakeGitHub())
    pusher = kwargs.pop("pusher", FakePush())
    stdout = kwargs.pop("stdout", io.StringIO())
    stderr = kwargs.pop("stderr", io.StringIO())
    env = kwargs.pop("environ", {"FORGE_GITHUB_TOKEN": "test-token"})
    code = run_submit(
        repo=kwargs.pop("repo", REPO),
        title=kwargs.pop("title", TITLE),
        head=kwargs.pop("head", HEAD),
        urlopen=fake.urlopen,
        base_url=FAKE_API,
        stdout=stdout,
        stderr=stderr,
        environ=env,
        pusher=pusher,
        **kwargs,
    )
    return code, stdout.getvalue(), stderr.getvalue(), fake, pusher


class DryRunTests(unittest.TestCase):
    def test_dry_run_prints_plan_and_does_not_push(self) -> None:
        code, out, err, fake, pusher = _submit(dry_run=True, environ={})
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("dry-run", out)
        self.assertIn(f"head: {HEAD}", out)
        self.assertIn("base: main", out)
        self.assertIn(f"title: {TITLE}", out)
        for heading in BODY_HEADINGS:
            self.assertIn(heading, out)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_cli_dry_run(self) -> None:
        fake = FakeGitHub()
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["submit", "--repo", REPO, "--title", TITLE, "--dry-run"],
            urlopen=fake.urlopen,
            environ={},
            stdout=stdout,
            stderr=stderr,
            base_url=FAKE_API,
        )
        # CLI dry-run uses real git HEAD (this workshop branch), which is not protect.
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertIn("dry-run", stdout.getvalue())
        self.assertEqual(fake.writes(), [])

    def test_title_must_pass_pr_title(self) -> None:
        code, _out, err, fake, pusher = _submit(dry_run=True, title="not a title", environ={})
        self.assertEqual(code, EXIT_CONFIG)
        self.assertTrue(err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])
        lint_code, _, _ = lint_title(TITLE)
        self.assertEqual(lint_code, EXIT_OK)
        lint_code, _, _ = lint_title(EXAMPLE)
        self.assertEqual(lint_code, EXIT_OK)


class RefuseTests(unittest.TestCase):
    def test_protect_head_is_refused(self) -> None:
        code, _out, err, fake, pusher = _submit(head="main", dry_run=True, environ={})
        self.assertEqual(code, EXIT_CONFIG)
        self.assertIn("protect", err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_learning_guide_portal_is_refused(self) -> None:
        code, _out, err, fake, pusher = _submit(
            repo="First-Light-TechHK/LearningGuidePortal",
            dry_run=True,
            environ={},
        )
        self.assertEqual(code, EXIT_CONFIG)
        self.assertIn("refusing", err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_missing_token_exits_2_without_push(self) -> None:
        code, _out, err, fake, pusher = _submit(environ={})
        self.assertEqual(code, EXIT_AUTH)
        self.assertIn("missing", err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])


class LiveFakeApiTests(unittest.TestCase):
    def test_opens_draft_pr_and_never_merges(self) -> None:
        code, out, err, fake, pusher = _submit()
        self.assertEqual(code, EXIT_OK, err)
        self.assertEqual(pusher.calls, [("origin", HEAD)])
        self.assertEqual(fake.methods().count("POST"), 1)
        self.assertIn("opened draft PR #1", out)
        self.assertEqual(len(fake.pulls), 1)
        self.assertTrue(fake.pulls[0]["draft"])
        self.assertEqual(fake.pulls[0]["title"], TITLE)
        self.assertEqual(fake.pulls[0]["head"]["ref"], HEAD)
        self.assertFalse(any("/merge" in path for _method, path, _body in fake.calls))
        self.assertEqual([c for c in fake.calls if c[0] in {"POST", "PUT"} and "rulesets" in c[1]], [])

    def test_second_submit_patches_existing(self) -> None:
        fake = FakeGitHub()
        pusher = FakePush()
        first, _out1, err1, _, _ = _submit(fake=fake, pusher=pusher)
        self.assertEqual(first, EXIT_OK, err1)
        second, out2, err2, _, _ = _submit(fake=fake, pusher=pusher)
        self.assertEqual(second, EXIT_OK, err2)
        self.assertEqual(fake.methods().count("POST"), 1)
        self.assertEqual(fake.methods().count("PATCH"), 1)
        self.assertIn("updated draft PR #1", out2)
        self.assertEqual(len(fake.pulls), 1)
        self.assertFalse(any("/merge" in path for _method, path, _body in fake.calls))


class WorkshopCiTests(unittest.TestCase):
    def test_overlay_check_does_not_live_submit(self) -> None:
        root = Path(__file__).resolve().parents[2]
        command = (root / "suites" / "forge-apply" / "suite.yaml").read_text(encoding="utf-8")
        self.assertIn("forge submit", command)
        self.assertIn("--dry-run", command)
        overlay = (root / ".github" / "workflows" / "overlay-check.yml").read_text(encoding="utf-8")
        self.assertNotIn("forge submit", overlay)
        self.assertNotIn("python -m forge submit", overlay)


if __name__ == "__main__":
    unittest.main()
