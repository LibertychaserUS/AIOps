"""开发侧代推：check, then git push, then gh pr create.

Aligns with GitHub CLI `gh pr create`:
https://cli.github.com/manual/gh_pr_create

Forge does not store secrets. It only consumes a host-injected GitHub write
credential (gh auth login, GH_TOKEN, or git https extraheader). See
docs/submit-credential.md.

Does not clone Graphite (no stacks, no merge-when-ready). Never merges.
Never applies a Ruleset. CI must not call this command.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TextIO

from forge import EXIT_API, EXIT_AUTH, EXIT_CONFIG, EXIT_OK
from forge.apply import (
    DEFAULT_PROTECT,
    ForgeError,
    assert_apply_allowed,
    load_config,
    normalize_branch,
    parse_repo,
)
from forge.check import EXIT_CHECK, run_check
from forge.credential import (
    MISSING_MESSAGE,
    WriteCredential,
    probe_write_credential,
    redact_secrets,
)
from forge.title import EXAMPLE, GRAMMAR, lint_title

BODY_HEADINGS = (
    "做了什么",
    "为什么",
    "动了哪些门",
    "怎么验",
    "不做什么",
    "分工",
)

DEFAULT_REMOTE = "origin"
GitRunner = Callable[..., str]
Pusher = Callable[[str, str], None]
GhRunner = Callable[..., str]
PrCreate = Callable[..., tuple[str, int]]
CredentialProbe = Callable[[], WriteCredential]
CheckFn = Callable[..., int]


def default_git_runner(
    args: Sequence[str],
    cwd: Path | str | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
) -> str:
    env = None if environ is None else dict(environ)
    result = subprocess.run(
        ["git", *args],
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        err = redact_secrets((result.stderr or result.stdout or "").strip()) or f"exit {result.returncode}"
        raise ForgeError(EXIT_CONFIG, f"git {' '.join(args[:3])} failed: {err}")
    return (result.stdout or "").strip()


def default_pusher(
    remote: str,
    ref: str,
    *,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
) -> None:
    if git_runner is None:
        default_git_runner(["push", "-u", remote, ref], cwd=cwd, environ=environ)
        return
    git_runner(["push", "-u", remote, ref], cwd=cwd)


def default_gh_runner(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
) -> str:
    env = dict(os.environ if environ is None else environ)
    env.pop("GH_DEBUG", None)
    env.pop("GH_TRACE", None)
    result = subprocess.run(
        ["gh", *args],
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        err = redact_secrets((result.stderr or result.stdout or "").strip()) or f"exit {result.returncode}"
        raise ForgeError(EXIT_API, f"gh {' '.join(args[:3])} failed: {err}")
    return (result.stdout or "").strip()


def resolve_head(
    head: str | None,
    *,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
) -> str:
    if head and head.strip():
        return normalize_branch(head)
    runner = default_git_runner if git_runner is None else git_runner
    raw = runner(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if not raw or raw == "HEAD":
        raise ForgeError(EXIT_CONFIG, "refusing detached HEAD; pass a feature branch")
    return normalize_branch(raw)


def resolve_commit_subject(
    *,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
) -> str | None:
    runner = default_git_runner if git_runner is None else git_runner
    try:
        subject = runner(["log", "-1", "--format=%s"], cwd=cwd)
    except ForgeError:
        return None
    return subject or None


def intended_title(explicit: str | None, commit_subject: str | None) -> str:
    if explicit is not None:
        return explicit
    if commit_subject:
        code, _, _ = lint_title(commit_subject)
        if code == EXIT_OK:
            return commit_subject
    raise ForgeError(
        EXIT_CONFIG,
        f"missing --title (must pass python -m forge pr-title; {GRAMMAR}; example: {EXAMPLE})",
    )


def assert_head_not_protect(head: str, protect: Sequence[str]) -> None:
    locked = {normalize_branch(item) for item in protect}
    if head in locked:
        raise ForgeError(EXIT_CONFIG, f"refusing to submit protect branch {head!r}")


def pr_body() -> str:
    return "".join(f"## {heading}\n\n" for heading in BODY_HEADINGS)


def parse_pr_number(text: str) -> int:
    match = re.search(r"/pull/(\d+)", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d+)\b", text)
    if match:
        return int(match.group(1))
    raise ForgeError(EXIT_API, "gh pr create did not print a pull number")


def default_open_or_update_pr(
    *,
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str,
    cwd: Path | str | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
    gh_runner: GhRunner | None = None,
) -> tuple[str, int]:
    runner = gh_runner

    def run(args: Sequence[str]) -> str:
        if runner is None:
            return default_gh_runner(args, cwd=cwd, environ=environ)
        return runner(args)

    raw = run(
        ["pr", "list", "--repo", repo, "--head", head, "--state", "open", "--json", "number"]
    )
    try:
        listed = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise ForgeError(EXIT_API, f"gh pr list returned non-JSON: {exc}") from exc
    if isinstance(listed, list) and listed:
        first = listed[0]
        if isinstance(first, dict) and first.get("number") is not None:
            number = int(first["number"])
            run(["pr", "edit", str(number), "--repo", repo, "--title", title, "--body", body])
            return "updated", number
    created = run(
        [
            "pr",
            "create",
            "--repo",
            repo,
            "--head",
            head,
            "--base",
            base,
            "--title",
            title,
            "--body",
            body,
            "--draft",
        ]
    )
    return "opened", parse_pr_number(created)


def _print_plan(
    *,
    stdout: TextIO,
    repo: str,
    head: str,
    base: str,
    title: str,
    dry_run: bool,
    credential: WriteCredential,
) -> None:
    if dry_run:
        print("dry-run", file=stdout)
    print(f"repo: {repo}", file=stdout)
    print(f"remote: {DEFAULT_REMOTE}", file=stdout)
    print(f"head: {head}", file=stdout)
    print(f"base: {base}", file=stdout)
    print(f"title: {title}", file=stdout)
    print(f"credential: {credential.source}", file=stdout)
    print("body headings:", file=stdout)
    for heading in BODY_HEADINGS:
        print(f"  {heading}", file=stdout)


def run_submit(
    *,
    repo: str,
    title: str | None = None,
    dry_run: bool = False,
    path: Path | str | None = None,
    head: str | None = None,
    base: str | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
    pusher: Pusher | None = None,
    check_fn: CheckFn | None = None,
    check_root: Path | str | None = None,
    credential_probe: CredentialProbe | None = None,
    pr_create: PrCreate | None = None,
    gh_runner: GhRunner | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    env = environ
    try:
        owner, name = parse_repo(repo)
        assert_apply_allowed(owner, name)
        config_path = None if path is None else Path(path)
        config = load_config(config_path)
        resolved_head = resolve_head(head, cwd=cwd, git_runner=git_runner)
        assert_head_not_protect(resolved_head, config.protect)
        resolved_base = (
            normalize_branch(base)
            if base and base.strip()
            else (config.protect[0] if config.protect else DEFAULT_PROTECT[0])
        )
        subject = None if title is not None else resolve_commit_subject(
            cwd=cwd, git_runner=git_runner
        )
        resolved_title = intended_title(title, subject)
        code, message, _parts = lint_title(resolved_title)
        if code != EXIT_OK:
            raise ForgeError(EXIT_CONFIG, message)

        cred = (
            credential_probe()
            if credential_probe is not None
            else probe_write_credential(environ=env, cwd=cwd)
        )
        if not cred.present:
            print(MISSING_MESSAGE, file=err)
            return EXIT_AUTH

        checker = run_check if check_fn is None else check_fn
        root = Path(".") if check_root is None and cwd is None else Path(check_root or cwd)
        check_code = checker(
            root,
            title=resolved_title,
            stdout=out,
            stderr=err,
            environ=env,
        )
        if check_code != EXIT_OK:
            print("forge submit: refusing (local check is red); no push, no PR", file=err)
            return EXIT_CHECK

        _print_plan(
            stdout=out,
            repo=f"{owner}/{name}",
            head=resolved_head,
            base=resolved_base,
            title=resolved_title,
            dry_run=dry_run,
            credential=cred,
        )
        if dry_run:
            return EXIT_OK

        push = pusher
        if push is None:

            def push(remote: str, ref: str) -> None:
                default_pusher(remote, ref, cwd=cwd, git_runner=git_runner, environ=env)

        push(DEFAULT_REMOTE, resolved_head)
        print(f"pushed {DEFAULT_REMOTE} {resolved_head}", file=out)

        create = pr_create if pr_create is not None else default_open_or_update_pr
        action, number = create(
            repo=f"{owner}/{name}",
            head=resolved_head,
            base=resolved_base,
            title=resolved_title,
            body=pr_body(),
            cwd=cwd,
            environ=env,
            gh_runner=gh_runner,
        )
        print(f"{action} draft PR #{number}", file=out)
        return EXIT_OK
    except ForgeError as exc:
        print(redact_secrets(exc.message), file=err)
        return exc.code
