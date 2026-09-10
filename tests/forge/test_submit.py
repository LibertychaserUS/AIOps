"""Forge submit with fakes. No live GitHub writes. No Forge-owned submit token."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from forge import EXIT_AUTH, EXIT_CONFIG, EXIT_OK
from forge.__main__ import main
from forge.check import EXIT_CHECK
from forge.credential import MISSING_MESSAGE, WriteCredential
from forge.submit import BODY_HEADINGS, run_submit
from forge.title import EXAMPLE, lint_title

REPO = "acme/widget"
HEAD = "cursor/feature"
TITLE = "feat(forge/dev): add submit middleware"
ROOT = Path(__file__).resolve().parents[2]


class FakePush:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, remote: str, ref: str) -> None:
        self.calls.append((remote, ref))


class FakePr:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.number = 0

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if "merge" in str(kwargs).lower():
            raise AssertionError("submit must never merge")
        if self.number:
            return "updated", self.number
        self.number = 1
        return "opened", 1


def _present() -> WriteCredential:
    return WriteCredential(True, "gh-login", "test")


def _missing() -> WriteCredential:
    return WriteCredential(False, "none", "no usable GitHub write credential")


def _ok_check(*_args, **_kwargs):
    return EXIT_OK


def _red_check(*_args, **_kwargs):
    return EXIT_CHECK


def _submit(**kwargs):
    pusher = kwargs.pop("pusher", FakePush())
    pr_create = kwargs.pop("pr_create", FakePr())
    stdout = kwargs.pop("stdout", io.StringIO())
    stderr = kwargs.pop("stderr", io.StringIO())
    env = kwargs.pop("environ", {})
    kwargs.setdefault("check_fn", _ok_check)
    kwargs.setdefault("credential_probe", _present)
    code = run_submit(
        repo=kwargs.pop("repo", REPO),
        title=kwargs.pop("title", TITLE),
        head=kwargs.pop("head", HEAD),
        stdout=stdout,
        stderr=stderr,
        environ=env,
        pusher=pusher,
        pr_create=pr_create,
        **kwargs,
    )
    return code, stdout.getvalue(), stderr.getvalue(), pusher, pr_create


class DryRunTests(unittest.TestCase):
    def test_dry_run_without_credential_is_red(self) -> None:
        code, out, err, pusher, pr_create = _submit(
            dry_run=True,
            credential_probe=_missing,
        )
        self.assertEqual(code, EXIT_AUTH)
        self.assertIn("no usable GitHub write credential", err)
        self.assertIn("gh auth login", err)
        self.assertNotIn("dry-run", out)
        self.assertEqual(pusher.calls, [])
        self.assertEqual(pr_create.calls, [])

    def test_dry_run_with_host_cred_prints_plan_and_does_not_push(self) -> None:
        code, out, err, pusher, pr_create = _submit(dry_run=True)
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("dry-run", out)
        self.assertIn(f"head: {HEAD}", out)
        self.assertIn("base: main", out)
        self.assertIn(f"title: {TITLE}", out)
        self.assertIn("credential: gh-login", out)
        for heading in BODY_HEADINGS:
            self.assertIn(heading, out)
        self.assertEqual(pusher.calls, [])
        self.assertEqual(pr_create.calls, [])

    def test_cli_dry_run_without_credential_is_red(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["submit", "--repo", REPO, "--title", TITLE, "--head", HEAD, "--dry-run"],
            environ={"GITHUB_ACTIONS": "true"},
            stdout=stdout,
            stderr=stderr,
            check_fn=_ok_check,
        )
        self.assertEqual(code, EXIT_AUTH, stdout.getvalue())
        self.assertIn("no usable GitHub write credential", stderr.getvalue())
        self.assertNotIn("dry-run", stdout.getvalue())

    def test_cli_dry_run_with_host_cred(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["submit", "--repo", REPO, "--title", TITLE, "--head", HEAD, "--dry-run"],
            environ={},
            stdout=stdout,
            stderr=stderr,
            check_fn=_ok_check,
            credential_probe=_present,
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertIn("dry-run", stdout.getvalue())
        self.assertIn("credential: gh-login", stdout.getvalue())

    def test_title_must_pass_pr_title(self) -> None:
        code, _out, err, pusher, pr_create = _submit(dry_run=True, title="not a title")
        self.assertEqual(code, EXIT_CONFIG)
        self.assertTrue(err)
        self.assertEqual(pusher.calls, [])
        self.assertEqual(pr_create.calls, [])
        lint_code, _, _ = lint_title(TITLE)
        self.assertEqual(lint_code, EXIT_OK)
        lint_code, _, _ = lint_title(EXAMPLE)
        self.assertEqual(lint_code, EXIT_OK)

    def test_red_check_blocks_dry_run(self) -> None:
        code, out, err, pusher, pr_create = _submit(dry_run=True, check_fn=_red_check)
        self.assertEqual(code, EXIT_CHECK)
        self.assertIn("refusing", err)
        self.assertIn("check is red", err)
        self.assertNotIn("dry-run", out)
        self.assertEqual(pusher.calls, [])
        self.assertEqual(pr_create.calls, [])


class RefuseTests(unittest.TestCase):
    def test_protect_head_is_refused(self) -> None:
        code, _out, err, pusher, pr_create = _submit(head="main", dry_run=True)
        self.assertEqual(code, EXIT_CONFIG)
        self.assertIn("protect", err)
        self.assertEqual(pusher.calls, [])
        self.assertEqual(pr_create.calls, [])

    def test_learning_guide_portal_is_refused(self) -> None:
        code, _out, err, pusher, pr_create = _submit(
            repo="First-Light-TechHK/LearningGuidePortal",
            dry_run=True,
        )
        self.assertEqual(code, EXIT_CONFIG)
        self.assertIn("refusing", err)
        self.assertEqual(pusher.calls, [])
        self.assertEqual(pr_create.calls, [])

    def test_missing_credential_exits_2_without_push(self) -> None:
        code, _out, err, pusher, pr_create = _submit(credential_probe=_missing)
        self.assertEqual(code, EXIT_AUTH)
        self.assertIn("no usable GitHub write credential", err)
        self.assertIn("gh auth login", err)
        self.assertEqual(pusher.calls, [])
        self.assertEqual(pr_create.calls, [])

    def test_github_token_env_is_not_a_submit_story(self) -> None:
        code, _out, err, pusher, pr_create = _submit(
            credential_probe=_missing,
            environ={"GITHUB_TOKEN": "ci-token", "FORGE_GITHUB_TOKEN": "ops-token"},
        )
        self.assertEqual(code, EXIT_AUTH)
        self.assertIn(MISSING_MESSAGE.splitlines()[0], err)
        self.assertEqual(pusher.calls, [])
        self.assertEqual(pr_create.calls, [])

    def test_red_check_blocks_live_push(self) -> None:
        code, _out, err, pusher, pr_create = _submit(check_fn=_red_check)
        self.assertEqual(code, EXIT_CHECK)
        self.assertIn("refusing", err)
        self.assertEqual(pusher.calls, [])
        self.assertEqual(pr_create.calls, [])


class LiveFakeGhTests(unittest.TestCase):
    def test_opens_draft_pr_and_never_merges(self) -> None:
        code, out, err, pusher, pr_create = _submit()
        self.assertEqual(code, EXIT_OK, err)
        self.assertEqual(pusher.calls, [("origin", HEAD)])
        self.assertEqual(len(pr_create.calls), 1)
        self.assertEqual(pr_create.calls[0]["head"], HEAD)
        self.assertEqual(pr_create.calls[0]["title"], TITLE)
        self.assertIn("opened draft PR #1", out)
        self.assertIn("## 做了什么", pr_create.calls[0]["body"])
        self.assertFalse(any("merge" in str(call).lower() for call in pr_create.calls))

    def test_second_submit_updates_existing(self) -> None:
        pusher = FakePush()
        pr_create = FakePr()
        first, _out1, err1, _, _ = _submit(pusher=pusher, pr_create=pr_create)
        self.assertEqual(first, EXIT_OK, err1)
        second, out2, err2, _, _ = _submit(pusher=pusher, pr_create=pr_create)
        self.assertEqual(second, EXIT_OK, err2)
        self.assertEqual(len(pr_create.calls), 2)
        self.assertIn("updated draft PR #1", out2)


class WorkshopCiTests(unittest.TestCase):
    def test_ci_does_not_call_forge_submit(self) -> None:
        suite = (ROOT / "suites" / "forge-apply" / "suite.yaml").read_text(encoding="utf-8")
        self.assertNotIn("python -m forge submit", suite)
        self.assertNotIn("FORGE_SUBMIT_TOKEN", suite)
        for name in (
            "overlay-check.yml",
            "overlay.yml",
            "pr-title.yml",
            "sop-lock.yml",
            "forge-check.yml",
        ):
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertNotIn("python -m forge submit", text)

    def test_submit_source_does_not_invent_a_forge_token(self) -> None:
        text = (ROOT / "forge" / "submit.py").read_text(encoding="utf-8")
        self.assertNotIn("FORGE_SUBMIT_TOKEN", text)
        self.assertNotIn("resolve_token(", text)
        self.assertIn("gh pr create", text)
        self.assertIn("probe_write_credential", text)


if __name__ == "__main__":
    unittest.main()
