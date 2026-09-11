"""Forge submit against a fake Pulls API. Never talks to a real repo. Never merges."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from forge import EXIT_AUTH, EXIT_CONFIG, EXIT_OK, SUBMIT_TOKEN_ENV
from forge.__main__ import main
from forge.check import EXIT_CHECK
from forge.submit import (
    BODY_HEADINGS,
    GITHUB_HTTPS_EXTRAHEADER,
    MISSING_SUBMIT_TOKEN,
    REQUIRE_SUBMIT_TOKEN,
    default_pusher,
    run_submit,
)
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


def _ok_check(*_args, **_kwargs):
    return EXIT_OK


def _red_check(*_args, **_kwargs):
    return EXIT_CHECK


def _submit(**kwargs):
    fake = kwargs.pop("fake", FakeGitHub())
    pusher = kwargs.pop("pusher", FakePush())
    stdout = kwargs.pop("stdout", io.StringIO())
    stderr = kwargs.pop("stderr", io.StringIO())
    env = kwargs.pop("environ", {SUBMIT_TOKEN_ENV: "test-token"})
    kwargs.setdefault("check_fn", _ok_check)
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
    def test_dry_run_without_token_is_red(self) -> None:
        code, out, err, fake, pusher = _submit(dry_run=True, environ={})
        self.assertEqual(code, EXIT_AUTH)
        self.assertIn("dry-run", out)
        self.assertIn(REQUIRE_SUBMIT_TOKEN, out)
        self.assertIn(MISSING_SUBMIT_TOKEN, err)
        self.assertIn(f"head: {HEAD}", out)
        self.assertIn("base: dev", out)
        self.assertIn(f"title: {TITLE}", out)
        for heading in BODY_HEADINGS:
            self.assertIn(heading, out)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_dry_run_with_submit_token_prints_plan_and_does_not_push(self) -> None:
        code, out, err, fake, pusher = _submit(dry_run=True)
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("dry-run", out)
        self.assertIn(REQUIRE_SUBMIT_TOKEN, out)
        self.assertIn(f"head: {HEAD}", out)
        self.assertIn("base: dev", out)
        self.assertIn(f"title: {TITLE}", out)
        for heading in BODY_HEADINGS:
            self.assertIn(heading, out)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_cli_dry_run_without_token_is_red(self) -> None:
        fake = FakeGitHub()
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["submit", "--repo", REPO, "--title", TITLE, "--head", HEAD, "--dry-run"],
            urlopen=fake.urlopen,
            environ={},
            stdout=stdout,
            stderr=stderr,
            base_url=FAKE_API,
            check_fn=_ok_check,
        )
        self.assertEqual(code, EXIT_AUTH, stdout.getvalue())
        self.assertIn(REQUIRE_SUBMIT_TOKEN, stdout.getvalue())
        self.assertIn(MISSING_SUBMIT_TOKEN, stderr.getvalue())
        self.assertEqual(fake.writes(), [])

    def test_cli_dry_run_with_submit_token(self) -> None:
        fake = FakeGitHub()
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["submit", "--repo", REPO, "--title", TITLE, "--head", HEAD, "--dry-run"],
            urlopen=fake.urlopen,
            environ={SUBMIT_TOKEN_ENV: "forge-submit-ci-dry-run"},
            stdout=stdout,
            stderr=stderr,
            base_url=FAKE_API,
            check_fn=_ok_check,
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertIn("dry-run", stdout.getvalue())
        self.assertIn(REQUIRE_SUBMIT_TOKEN, stdout.getvalue())
        self.assertNotIn("forge-submit-ci-dry-run", stdout.getvalue())
        self.assertNotIn("forge-submit-ci-dry-run", stderr.getvalue())
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

    def test_red_check_blocks_dry_run(self) -> None:
        code, _out, err, fake, pusher = _submit(
            dry_run=True,
            check_fn=_red_check,
            environ={},
        )
        self.assertEqual(code, EXIT_CHECK)
        self.assertIn("refusing", err)
        self.assertIn("check is red", err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])


class RefuseTests(unittest.TestCase):
    def test_non_protect_base_is_refused(self) -> None:
        code, _out, err, fake, pusher = _submit(
            base="cursor/overlay-architecture-6842",
            dry_run=True,
            environ={SUBMIT_TOKEN_ENV: "t"},
        )
        self.assertEqual(code, EXIT_CONFIG)
        self.assertIn("protect", err)
        self.assertIn("封顶", err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

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

    def test_fork_learning_guide_submit_stays_allowed(self) -> None:
        # Developers submit draft PRs to the fork; only live apply / release refuse it.
        code, out, err, fake, pusher = _submit(
            repo="LibertychaserUS/LearningGuidePortal",
            dry_run=True,
        )
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("dry-run", out)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_missing_token_exits_2_without_push(self) -> None:
        code, out, err, fake, pusher = _submit(environ={})
        self.assertEqual(code, EXIT_AUTH)
        self.assertIn(MISSING_SUBMIT_TOKEN, err)
        self.assertNotIn("GITHUB_TOKEN", err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_github_token_alone_is_not_enough(self) -> None:
        code, _out, err, fake, pusher = _submit(
            environ={"GITHUB_TOKEN": "ci-token", "FORGE_GITHUB_TOKEN": "ops-token"}
        )
        self.assertEqual(code, EXIT_AUTH)
        self.assertIn(MISSING_SUBMIT_TOKEN, err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_empty_submit_token_is_not_enough(self) -> None:
        code, _out, err, fake, pusher = _submit(environ={SUBMIT_TOKEN_ENV: "   "})
        self.assertEqual(code, EXIT_AUTH)
        self.assertIn(MISSING_SUBMIT_TOKEN, err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_red_check_blocks_live_push(self) -> None:
        leak = "secret-token-do-not-leak-9f3a"
        code, out, err, fake, pusher = _submit(
            check_fn=_red_check,
            environ={SUBMIT_TOKEN_ENV: leak},
        )
        self.assertEqual(code, EXIT_CHECK)
        self.assertIn("refusing", err)
        self.assertIn("check is red", err)
        self.assertNotIn(leak, out)
        self.assertNotIn(leak, err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])


class LiveFakeApiTests(unittest.TestCase):
    def test_opens_draft_pr_and_never_merges(self) -> None:
        leak = "secret-token-do-not-leak-9f3a"
        code, out, err, fake, pusher = _submit(environ={SUBMIT_TOKEN_ENV: leak})
        self.assertEqual(code, EXIT_OK, err)
        self.assertEqual(pusher.calls, [("origin", HEAD)])
        self.assertEqual(fake.methods().count("POST"), 1)
        self.assertIn("opened draft PR #1", out)
        self.assertEqual(len(fake.pulls), 1)
        self.assertTrue(fake.pulls[0]["draft"])
        self.assertEqual(fake.pulls[0]["title"], TITLE)
        self.assertEqual(fake.pulls[0]["head"]["ref"], HEAD)
        self.assertNotIn(leak, out)
        self.assertNotIn(leak, err)
        self.assertNotIn(leak, fake.pulls[0]["body"] or "")
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


class HeadResolutionTests(unittest.TestCase):
    def test_detached_head_is_refused(self) -> None:
        def git(args, cwd=None):
            if args[:2] == ["rev-parse", "--abbrev-ref"]:
                return "HEAD"
            raise AssertionError(args)

        code, _out, err, fake, pusher = _submit(
            dry_run=True,
            head=None,
            git_runner=git,
            environ={SUBMIT_TOKEN_ENV: "t"},
        )
        self.assertEqual(code, EXIT_CONFIG)
        self.assertIn("detached HEAD", err)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_github_head_ref_used_when_detached(self) -> None:
        def git(args, cwd=None):
            if args[:2] == ["rev-parse", "--abbrev-ref"]:
                return "HEAD"
            raise AssertionError(args)

        code, out, err, fake, pusher = _submit(
            dry_run=True,
            head=None,
            git_runner=git,
            environ={SUBMIT_TOKEN_ENV: "t", "GITHUB_HEAD_REF": HEAD},
        )
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn(f"head: {HEAD}", out)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])


class TokenPushTests(unittest.TestCase):
    def test_default_pusher_injects_submit_token(self) -> None:
        recorded: list[list[str]] = []

        def git(args, cwd=None):
            recorded.append(list(args))
            return ""

        leak = "secret-token-do-not-leak-push"
        default_pusher("origin", HEAD, git_runner=git, token=leak)
        self.assertEqual(len(recorded), 1)
        self.assertIn("-c", recorded[0])
        self.assertIn(f"{GITHUB_HTTPS_EXTRAHEADER}=AUTHORIZATION: bearer {leak}", recorded[0])
        self.assertEqual(recorded[0][-4:], ["push", "-u", "origin", HEAD])

    def test_submit_default_pusher_uses_submit_token(self) -> None:
        recorded: list[list[str]] = []

        def git(args, cwd=None):
            recorded.append(list(args))
            return ""

        leak = "secret-token-do-not-leak-push"
        fake = FakeGitHub()
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_submit(
            repo=REPO,
            title=TITLE,
            head=HEAD,
            urlopen=fake.urlopen,
            base_url=FAKE_API,
            stdout=stdout,
            stderr=stderr,
            environ={SUBMIT_TOKEN_ENV: leak},
            git_runner=git,
            check_fn=_ok_check,
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertTrue(any("push" in args for args in recorded))
        joined = " ".join(part for args in recorded for part in args)
        self.assertIn(f"AUTHORIZATION: bearer {leak}", joined)
        self.assertNotIn(leak, stdout.getvalue())
        self.assertNotIn(leak, stderr.getvalue())

    def test_submit_passes_pr_body_to_check(self) -> None:
        seen: dict[str, object] = {}

        def spy(_root, **kwargs):
            seen.update(kwargs)
            return EXIT_OK

        code, _out, err, fake, pusher = _submit(dry_run=True, check_fn=spy)
        self.assertEqual(code, EXIT_OK, err)
        body = str(seen.get("body") or "")
        for heading in BODY_HEADINGS:
            self.assertIn(heading, body)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])


class WorkshopCiTests(unittest.TestCase):
    def test_overlay_and_forge_workflows_do_not_submit(self) -> None:
        root = Path(__file__).resolve().parents[2]
        suite = (root / "suites" / "forge-apply" / "suite.yaml").read_text(encoding="utf-8")
        self.assertIn("status: blocked", suite)
        self.assertNotIn("python -m forge submit", suite)
        for name in (
            "ci.yml",
            "overlay-check.yml",
            "overlay.yml",
            "forge-check.yml",
            "release.yml",
        ):
            text = (root / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertNotIn("python -m forge submit", text)


if __name__ == "__main__":
    unittest.main()
