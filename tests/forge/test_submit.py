"""Forge submit against a fake Pulls API. Never talks to a real repo. Never merges."""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from forge.__main__ import main
from forge.apply import ForgeError
from forge.check import EXIT_CHECK
from forge.submit import (
    BODY_HEADINGS,
    GITHUB_HTTPS_EXTRAHEADER,
    MISSING_SUBMIT_TOKEN,
    REQUIRE_SUBMIT_TOKEN,
    default_git_runner,
    default_pusher,
    run_submit,
    token_git_env,
)
from forge.title import EXAMPLE, lint_title

from forge import EXIT_AUTH, EXIT_CONFIG, EXIT_OK, SUBMIT_TOKEN_ENV
from tests.forge.fake_github import FakeGitHub

FAKE_API = "https://forge.test"
REPO = "acme/widget"
HEAD = "cursor/feature"
TITLE = "feat(forge/dev): add submit middleware"
SHA = "0123456789abcdef0123456789abcdef01234567"
REFSPEC = f"{SHA}:refs/heads/{HEAD}"


class FakeGit:
    """Clean worktree checked out on `branch` at SHA. Records every call."""

    def __init__(self, branch: str = HEAD, *, dirty: str = "") -> None:
        self.branch = branch
        self.dirty = dirty
        self.calls: list[list[str]] = []
        self.envs: list[dict[str, str] | None] = []

    def __call__(self, args, cwd=None, env=None):
        self.calls.append(list(args))
        self.envs.append(None if env is None else dict(env))
        if args[:2] == ["rev-parse", "--abbrev-ref"]:
            return self.branch
        if args[:2] == ["rev-parse", "HEAD"]:
            return SHA
        if args[:1] == ["status"]:
            return self.dirty
        return ""


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
    head = kwargs.pop("head", HEAD)
    kwargs.setdefault("git_runner", FakeGit(head or HEAD))
    code = run_submit(
        repo=kwargs.pop("repo", REPO),
        title=kwargs.pop("title", TITLE),
        head=head,
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
            git_runner=FakeGit(),
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
            git_runner=FakeGit(),
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
        self.assertEqual(pusher.calls, [("origin", REFSPEC)])
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

    def test_open_pr_on_another_base_is_not_patched(self) -> None:
        fake = FakeGitHub()
        fake.pulls.append(
            {
                "number": 9,
                "title": "old",
                "body": "",
                "draft": True,
                "head": {"ref": HEAD},
                "base": {"ref": "main"},
            }
        )
        fake.next_pr = 10
        code, out, err, _, _ = _submit(fake=fake)
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("opened draft PR #10", out)
        self.assertEqual(fake.methods().count("POST"), 1)
        self.assertEqual(fake.methods().count("PATCH"), 0)
        opened = next(pull for pull in fake.pulls if pull["number"] == 10)
        self.assertEqual(opened["base"]["ref"], "dev")
        self.assertEqual(fake.pulls[0]["title"], "old")

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
        patch = next(body for method, _path, body in fake.calls if method == "PATCH")
        self.assertEqual(patch, {"title": TITLE})
        self.assertFalse(any("/merge" in path for _method, path, _body in fake.calls))

    def test_resubmit_keeps_the_authors_pr_body(self) -> None:
        fake = FakeGitHub()
        first, _out, err, _, _ = _submit(fake=fake)
        self.assertEqual(first, EXIT_OK, err)
        fake.pulls[0]["body"] = "## 做了什么\n\nwritten by the author\n"
        second, _out2, err2, _, _ = _submit(fake=fake)
        self.assertEqual(second, EXIT_OK, err2)
        self.assertEqual(fake.pulls[0]["body"], "## 做了什么\n\nwritten by the author\n")
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
        code, out, err, fake, pusher = _submit(
            dry_run=True,
            head=None,
            git_runner=FakeGit("HEAD"),
            environ={SUBMIT_TOKEN_ENV: "t", "GITHUB_HEAD_REF": HEAD},
        )
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn(f"head: {HEAD}", out)
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])


class WorktreeGuardTests(unittest.TestCase):
    def test_ref_like_heads_are_refused(self) -> None:
        for head in ("HEAD", "heads/dev", "refs/heads/dev", "refs/tags/x", "tags/forge-v1.0.0"):
            with self.subTest(head=head):
                code, _out, err, fake, pusher = _submit(head=head, git_runner=FakeGit(head))
                self.assertEqual(code, EXIT_CONFIG, err)
                self.assertIn("refusing --head", err)
                self.assertEqual(fake.calls, [])
                self.assertEqual(pusher.calls, [])

    def test_head_other_than_checked_out_branch_is_refused(self) -> None:
        seen: list[object] = []

        def spy(_root, **_kwargs):
            seen.append(_root)
            return EXIT_OK

        code, _out, err, fake, pusher = _submit(
            head="cursor/other",
            git_runner=FakeGit(HEAD),
            check_fn=spy,
        )
        self.assertEqual(code, EXIT_CONFIG, err)
        self.assertIn("checked-out branch", err)
        self.assertEqual(seen, [])
        self.assertEqual(fake.calls, [])
        self.assertEqual(pusher.calls, [])

    def test_explicit_head_on_detached_checkout_needs_matching_env(self) -> None:
        code, _out, err, _fake, pusher = _submit(dry_run=True, git_runner=FakeGit("HEAD"))
        self.assertEqual(code, EXIT_CONFIG, err)
        self.assertIn("detached HEAD", err)
        self.assertEqual(pusher.calls, [])

    def test_dirty_tree_is_refused_even_on_dry_run(self) -> None:
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run):
                code, _out, err, fake, pusher = _submit(
                    dry_run=dry_run,
                    git_runner=FakeGit(dirty="?? notes.txt"),
                )
                self.assertEqual(code, EXIT_CONFIG, err)
                self.assertIn("dirty worktree", err)
                self.assertEqual(fake.calls, [])
                self.assertEqual(pusher.calls, [])


def _sh(root: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    done = subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return done.stdout.strip()


class RealGitPushTests(unittest.TestCase):
    def _repo(self, tmp: str) -> tuple[Path, Path]:
        origin = Path(tmp) / "origin.git"
        work = Path(tmp) / "work"
        work.mkdir()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        (work / "README.md").write_text("x\n", encoding="utf-8")
        _sh(work, "init", "-q", "-b", "dev")
        _sh(work, "config", "user.email", "t@example.test")
        _sh(work, "config", "user.name", "T")
        _sh(work, "add", "-A")
        _sh(work, "commit", "-q", "-m", "init")
        _sh(work, "remote", "add", "origin", str(origin))
        _sh(work, "push", "-q", "origin", "dev")
        return work, origin

    def _run(self, work: Path, head: str | None) -> tuple[int, str]:
        stderr = io.StringIO()
        code = run_submit(
            repo=REPO,
            title=TITLE,
            head=head,
            urlopen=FakeGitHub().urlopen,
            base_url=FAKE_API,
            stdout=io.StringIO(),
            stderr=stderr,
            environ={SUBMIT_TOKEN_ENV: "t"},
            cwd=work,
            git_runner=lambda args, cwd=None, env=None: default_git_runner(args, cwd=work),
            check_fn=_ok_check,
        )
        return code, stderr.getvalue()

    def test_head_alias_never_moves_protect_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work, origin = self._repo(tmp)
            before = _sh(origin, "rev-parse", "dev")
            (work / "README.md").write_text("unreviewed\n", encoding="utf-8")
            _sh(work, "commit", "-q", "-am", "evil")
            for head in ("HEAD", "heads/dev"):
                code, err = self._run(work, head)
                self.assertEqual(code, EXIT_CONFIG, err)
            self.assertEqual(_sh(origin, "rev-parse", "dev"), before)

    def test_pushes_the_checked_sha_to_refs_heads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work, origin = self._repo(tmp)
            _sh(work, "checkout", "-q", "-b", HEAD)
            (work / "a.txt").write_text("a\n", encoding="utf-8")
            _sh(work, "add", "-A")
            _sh(work, "commit", "-q", "-m", "a")
            sha = _sh(work, "rev-parse", "HEAD")
            (work / "scratch.txt").write_text("untracked\n", encoding="utf-8")
            code, err = self._run(work, HEAD)
            self.assertEqual(code, EXIT_CONFIG, err)
            self.assertIn("dirty worktree", err)
            (work / "scratch.txt").unlink()
            code, err = self._run(work, HEAD)
            self.assertEqual(code, EXIT_OK, err)
            self.assertEqual(_sh(origin, "rev-parse", f"refs/heads/{HEAD}"), sha)
            self.assertEqual(_sh(work, "config", f"branch.{HEAD}.merge"), f"refs/heads/{HEAD}")


class TokenPushTests(unittest.TestCase):
    def test_default_pusher_injects_submit_token(self) -> None:
        git = FakeGit()
        leak = "secret-token-do-not-leak-push"
        default_pusher("origin", REFSPEC, git_runner=git, token=leak)
        self.assertEqual(git.calls[0], ["push", "origin", REFSPEC])
        self.assertNotIn(leak, " ".join(part for args in git.calls for part in args))
        env = git.envs[0] or {}
        n = int(os.environ.get("GIT_CONFIG_COUNT") or "0")
        self.assertEqual(env["GIT_CONFIG_COUNT"], str(n + 2))
        self.assertEqual(env[f"GIT_CONFIG_KEY_{n}"], GITHUB_HTTPS_EXTRAHEADER)
        self.assertEqual(env[f"GIT_CONFIG_VALUE_{n}"], "")
        self.assertEqual(env[f"GIT_CONFIG_KEY_{n + 1}"], GITHUB_HTTPS_EXTRAHEADER)
        self.assertEqual(env[f"GIT_CONFIG_VALUE_{n + 1}"], f"AUTHORIZATION: bearer {leak}")
        self.assertIn(["config", f"branch.{HEAD}.merge", f"refs/heads/{HEAD}"], git.calls)

    def test_token_env_appends_after_ambient_git_config(self) -> None:
        env = token_git_env("tok", {"GIT_CONFIG_COUNT": "1"})
        self.assertEqual(env["GIT_CONFIG_COUNT"], "3")
        self.assertEqual(env["GIT_CONFIG_VALUE_1"], "")
        self.assertEqual(env["GIT_CONFIG_VALUE_2"], "AUTHORIZATION: bearer tok")
        self.assertNotIn("GIT_CONFIG_KEY_0", env)

    def test_submit_default_pusher_uses_submit_token(self) -> None:
        git = FakeGit()
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
        self.assertIn(["push", "origin", REFSPEC], git.calls)
        joined = " ".join(part for args in git.calls for part in args)
        self.assertNotIn(leak, joined)
        pushed_env = git.envs[git.calls.index(["push", "origin", REFSPEC])] or {}
        self.assertIn(f"AUTHORIZATION: bearer {leak}", pushed_env.values())
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


class ApiBaseTests(unittest.TestCase):
    def _cli(self, api: str, command: list[str]) -> tuple[int, str, FakeGitHub]:
        fake = FakeGitHub()
        stderr = io.StringIO()
        code = main(
            command,
            urlopen=fake.urlopen,
            environ={SUBMIT_TOKEN_ENV: "t", "FORGE_GITHUB_TOKEN": "t", "FORGE_GITHUB_API": api},
            stdout=io.StringIO(),
            stderr=stderr,
            check_fn=_ok_check,
            pusher=FakePush(),
            git_runner=FakeGit(),
        )
        return code, stderr.getvalue(), fake

    def test_non_https_api_base_is_refused(self) -> None:
        submit = ["submit", "--repo", REPO, "--title", TITLE, "--head", HEAD]
        promote = ["promote", "--repo", REPO, "--from", "dev", "--to", "main"]
        for api in ("http://forge.test", "ftp://forge.test", "forge.test", "http://10.0.0.1:8080"):
            for command in (submit, promote):
                with self.subTest(api=api, command=command[0]):
                    code, err, fake = self._cli(api, command)
                    self.assertEqual(code, EXIT_CONFIG, err)
                    self.assertIn("must be https", err)
                    self.assertEqual(fake.calls, [])

    def test_https_and_loopback_http_are_allowed(self) -> None:
        for api in ("https://forge.test", "http://127.0.0.1:8765", "http://localhost:8765"):
            with self.subTest(api=api):
                code, err, _fake = self._cli(
                    api, ["submit", "--repo", REPO, "--title", TITLE, "--head", HEAD, "--dry-run"]
                )
                self.assertEqual(code, EXIT_OK, err)


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



class RedactionTests(unittest.TestCase):
    def test_git_failure_redacts_token_in_remote_url(self) -> None:
        leak = "ghp_mustNotAppear123"
        url = f"https://x-access-token:{leak}@github.com/acme/app.git"
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            default_git_runner(["remote", "add", "origin", url], cwd=tmp)
            # Second add fails locally (no network); the failing argv carries the URL.
            with self.assertRaises(ForgeError) as ctx:
                default_git_runner(["remote", "add", "origin", url], cwd=tmp)
        self.assertEqual(ctx.exception.code, EXIT_CONFIG)
        self.assertNotIn(leak, ctx.exception.message)
        self.assertIn("REDACTED", ctx.exception.message)

    def test_run_submit_redacts_error_messages(self) -> None:
        leak = "ghp_mustNotAppear456"

        def boom(args, cwd=None, env=None):
            raise ForgeError(EXIT_CONFIG, f"remote https://x:{leak}@github.com/a/b.git refused")

        out = io.StringIO()
        err = io.StringIO()
        code = run_submit(
            repo="acme/app",
            head="feature",
            title=EXAMPLE,
            environ={SUBMIT_TOKEN_ENV: "tok"},
            git_runner=boom,
            stdout=out,
            stderr=err,
            dry_run=True,
        )
        self.assertEqual(code, EXIT_CONFIG)
        self.assertNotIn(leak, err.getvalue())
        self.assertNotIn(leak, out.getvalue())


if __name__ == "__main__":
    unittest.main()
