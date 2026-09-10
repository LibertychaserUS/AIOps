"""开发侧代推：push the feature branch and open/update a draft PR.

Aligns with GitHub CLI `gh pr create` (push current branch + create PR):
https://cli.github.com/manual/gh_pr_create

Does not clone Graphite (no stacks, no merge-when-ready). Never merges.
Never applies a Ruleset. Ops (manage-repo + required checks) merges.

Requires env FORGE_SUBMIT_TOKEN (PAT / fine-grained / GitHub App token).
No GITHUB_TOKEN fallback, no FORGE_GITHUB_TOKEN fallback, no gh auth.
Missing or empty secret exits 2 even on --dry-run. Never print the token.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from forge import EXIT_AUTH, EXIT_CONFIG, EXIT_OK, SUBMIT_TOKEN_ENV
from forge.apply import (
    DEFAULT_API,
    DEFAULT_PROTECT,
    ForgeError,
    GitHubClient,
    UrlOpen,
    assert_apply_allowed,
    load_config,
    normalize_branch,
    parse_repo,
)
from forge.check import EXIT_CHECK, run_check
from forge.title import EXAMPLE, GRAMMAR, lint_title

MISSING_SUBMIT_TOKEN = f"missing {SUBMIT_TOKEN_ENV}"
REQUIRE_SUBMIT_TOKEN = f"would require {SUBMIT_TOKEN_ENV}"

BODY_HEADINGS = (
    "做了什么",
    "为什么",
    "动了哪些门",
    "怎么验",
    "不做什么",
    "分工",
)

DEFAULT_REMOTE = "origin"
GITHUB_HTTPS_EXTRAHEADER = "http.https://github.com/.extraheader"
GitRunner = Callable[..., str]
Pusher = Callable[[str, str], None]


def _redact_secrets(text: str) -> str:
    return re.sub(r"(AUTHORIZATION:\s*bearer\s+)\S+", r"\1[redacted]", text, flags=re.IGNORECASE)


def default_git_runner(
    args: Sequence[str],
    cwd: Path | str | None = None,
) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip() or f"exit {result.returncode}"
        shown = " ".join(_redact_secrets(part) for part in args)
        raise ForgeError(EXIT_CONFIG, f"git {shown} failed: {_redact_secrets(err)}")
    return (result.stdout or "").strip()


def default_pusher(
    remote: str,
    ref: str,
    *,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
    token: str | None = None,
) -> None:
    runner = default_git_runner if git_runner is None else git_runner
    args: list[str] = []
    if token:
        args.extend(["-c", f"{GITHUB_HTTPS_EXTRAHEADER}=AUTHORIZATION: bearer {token}"])
    args.extend(["push", "-u", remote, ref])
    runner(args, cwd=cwd)


def resolve_head(
    head: str | None,
    *,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
) -> str:
    if head and head.strip():
        return normalize_branch(head)
    runner = default_git_runner if git_runner is None else git_runner
    raw = runner(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if raw and raw != "HEAD":
        return normalize_branch(raw)
    env = {} if environ is None else environ
    for key in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
        candidate = str(env.get(key) or "").strip()
        if candidate and candidate != "HEAD":
            return normalize_branch(candidate)
    raise ForgeError(EXIT_CONFIG, "refusing detached HEAD; pass a feature branch")


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


def resolve_submit_token(
    environ: Mapping[str, str] | os._Environ[str] | None = None,
    explicit: str | None = None,
) -> str | None:
    """Require FORGE_SUBMIT_TOKEN. No GITHUB_TOKEN / FORGE_GITHUB_TOKEN / gh auth."""
    if explicit is not None:
        value = explicit.strip()
        return value or None
    env = os.environ if environ is None else environ
    raw = env.get(SUBMIT_TOKEN_ENV)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def pr_body() -> str:
    return "".join(f"## {heading}\n\n" for heading in BODY_HEADINGS)


def _print_plan(
    *,
    stdout: TextIO,
    repo: str,
    head: str,
    base: str,
    title: str,
    dry_run: bool,
) -> None:
    if dry_run:
        print("dry-run", file=stdout)
    print(f"repo: {repo}", file=stdout)
    print(f"remote: {DEFAULT_REMOTE}", file=stdout)
    print(f"head: {head}", file=stdout)
    print(f"base: {base}", file=stdout)
    print(f"title: {title}", file=stdout)
    print("body headings:", file=stdout)
    for heading in BODY_HEADINGS:
        print(f"  {heading}", file=stdout)


def _open_or_update_draft(
    client: GitHubClient,
    *,
    owner: str,
    name: str,
    head: str,
    base: str,
    title: str,
    body: str,
) -> tuple[str, int]:
    listed = client.request(
        "GET",
        f"/repos/{owner}/{name}/pulls?state=open&head={owner}:{head}&per_page=10",
    )
    existing: dict[str, Any] | None = None
    if isinstance(listed, list):
        for item in listed:
            if isinstance(item, dict):
                existing = item
                break
    if existing and existing.get("number") is not None:
        number = int(existing["number"])
        client.request(
            "PATCH",
            f"/repos/{owner}/{name}/pulls/{number}",
            {"title": title, "body": body},
        )
        return "updated", number
    created = client.request(
        "POST",
        f"/repos/{owner}/{name}/pulls",
        {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": True,
        },
    )
    if not isinstance(created, dict) or created.get("number") is None:
        raise ForgeError(EXIT_CONFIG, "GitHub API returned a non-object create result")
    return "opened", int(created["number"])


def run_submit(
    *,
    repo: str,
    title: str | None = None,
    dry_run: bool = False,
    path: Path | str | None = None,
    head: str | None = None,
    base: str | None = None,
    token: str | None = None,
    urlopen: UrlOpen | None = None,
    base_url: str = DEFAULT_API,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
    pusher: Pusher | None = None,
    check_fn: Any | None = None,
    check_root: Path | str | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    try:
        owner, name = parse_repo(repo)
        assert_apply_allowed(owner, name)
        config_path = None if path is None else Path(path)
        config = load_config(config_path)
        resolved_head = resolve_head(
            head, cwd=cwd, git_runner=git_runner, environ=environ
        )
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
        checker = run_check if check_fn is None else check_fn
        root = Path(".") if check_root is None and cwd is None else Path(check_root or cwd)
        check_code = checker(
            root,
            title=resolved_title,
            body=pr_body(),
            stdout=out,
            stderr=err,
            environ=environ,
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
        )
        print(REQUIRE_SUBMIT_TOKEN, file=out)
        if token is not None:
            resolved_token = token.strip() or None
        else:
            resolved_token = resolve_submit_token(environ)
        if not resolved_token:
            print(MISSING_SUBMIT_TOKEN, file=err)
            return EXIT_AUTH
        if dry_run:
            return EXIT_OK
        push = pusher
        if push is None:

            def push(remote: str, ref: str) -> None:
                default_pusher(
                    remote,
                    ref,
                    cwd=cwd,
                    git_runner=git_runner,
                    token=resolved_token,
                )

        push(DEFAULT_REMOTE, resolved_head)
        print(f"pushed {DEFAULT_REMOTE} {resolved_head}", file=out)
        client = GitHubClient(resolved_token, urlopen=urlopen, base_url=base_url)
        action, number = _open_or_update_draft(
            client,
            owner=owner,
            name=name,
            head=resolved_head,
            base=resolved_base,
            title=resolved_title,
            body=pr_body(),
        )
        print(f"{action} draft PR #{number}", file=out)
        return EXIT_OK
    except ForgeError as exc:
        print(exc.message, file=err)
        return exc.code
