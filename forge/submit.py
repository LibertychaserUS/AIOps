"""开发侧代推：push the feature branch and open/update a draft PR.

Aligns with GitHub CLI `gh pr create` (push current branch + create PR):
https://cli.github.com/manual/gh_pr_create

Does not clone Graphite (no merge-when-ready). Never merges.
Base is forge.yaml protect (default main): the PR is the squash 封顶.
Do not open onto another feature branch that will be squashed away.
Never applies a Ruleset. Ops (manage-repo + required checks) merges.

Requires env FORGE_SUBMIT_TOKEN (PAT / fine-grained / GitHub App token).
No GITHUB_TOKEN fallback, no FORGE_GITHUB_TOKEN fallback, no gh auth.
Missing or empty secret exits 2 even on --dry-run. Never print the token.

check runs on this worktree, so submit refuses a --head that is not the
checked-out branch and a dirty tree, then pushes the exact HEAD sha it
checked via an explicit `<sha>:refs/heads/<head>` refspec (no ref DWIM).
The token reaches git through GIT_CONFIG_* env, never argv.
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
    assert_submit_allowed,
    load_config,
    normalize_branch,
    parse_repo,
)
from forge.brief import REQUIRED_H2 as BODY_HEADINGS
from forge.check import EXIT_CHECK, run_check
from forge.title import EXAMPLE, GRAMMAR, lint_title

MISSING_SUBMIT_TOKEN = f"missing {SUBMIT_TOKEN_ENV}"
REQUIRE_SUBMIT_TOKEN = f"would require {SUBMIT_TOKEN_ENV}"

DEFAULT_REMOTE = "origin"
GITHUB_HTTPS_EXTRAHEADER = "http.https://github.com/.extraheader"
GitRunner = Callable[..., str]
Pusher = Callable[[str, str], None]
SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
# Names git would DWIM onto another ref (HEAD, heads/dev -> refs/heads/dev, ...).
AMBIGUOUS_HEAD_PREFIXES = ("heads/", "refs/", "tags/")


def _redact_secrets(text: str) -> str:
    return re.sub(r"(AUTHORIZATION:\s*bearer\s+)\S+", r"\1[redacted]", text, flags=re.IGNORECASE)


def default_git_runner(
    args: Sequence[str],
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=None if env is None else {**os.environ, **env},
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip() or f"exit {result.returncode}"
        shown = " ".join(_redact_secrets(part) for part in args)
        raise ForgeError(EXIT_CONFIG, f"git {shown} failed: {_redact_secrets(err)}")
    return (result.stdout or "").strip()


def token_git_env(
    token: str,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
) -> dict[str, str]:
    """GIT_CONFIG_* entries for the bearer header (git >= 2.31). Never argv (ps).

    Appended after any ambient GIT_CONFIG_COUNT entries. The empty value first
    resets inherited extraheaders (e.g. actions/checkout's GITHUB_TOKEN) so
    only FORGE_SUBMIT_TOKEN is sent.
    """
    env = os.environ if environ is None else environ
    try:
        start = max(int(str(env.get("GIT_CONFIG_COUNT") or "0")), 0)
    except ValueError:
        start = 0
    values = ("", f"AUTHORIZATION: bearer {token}")
    out = {"GIT_CONFIG_COUNT": str(start + len(values))}
    for offset, value in enumerate(values):
        out[f"GIT_CONFIG_KEY_{start + offset}"] = GITHUB_HTTPS_EXTRAHEADER
        out[f"GIT_CONFIG_VALUE_{start + offset}"] = value
    return out


def push_refspec(sha: str, head: str) -> str:
    return f"{sha}:refs/heads/{head}"


def default_pusher(
    remote: str,
    refspec: str,
    *,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
    token: str | None = None,
) -> None:
    runner = default_git_runner if git_runner is None else git_runner
    args = ["push", remote, refspec]
    if token:
        runner(args, cwd=cwd, env=token_git_env(token))
    else:
        runner(args, cwd=cwd)
    # `push -u` does not set upstream for a sha source; record it like -u would.
    _src, _sep, dest = refspec.partition(":")
    if dest.startswith("refs/heads/"):
        branch = dest[len("refs/heads/") :]
        runner(["config", f"branch.{branch}.remote", remote], cwd=cwd)
        runner(["config", f"branch.{branch}.merge", dest], cwd=cwd)


def submit_branch(name: str) -> str:
    """A plain branch name. HEAD and heads/ refs/ tags/ would resolve onto another ref."""
    text = name.strip()
    if text == "HEAD" or text.startswith(AMBIGUOUS_HEAD_PREFIXES):
        raise ForgeError(
            EXIT_CONFIG,
            f"refusing --head {name!r}; pass the plain feature branch name",
        )
    return normalize_branch(text)


def resolve_head(
    head: str | None,
    *,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
) -> str:
    """The checked-out branch (check runs on it). --head must name the same branch."""
    explicit = submit_branch(head) if head and head.strip() else None
    runner = default_git_runner if git_runner is None else git_runner
    raw = (runner(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd) or "").strip()
    current: str | None = None
    if raw and raw != "HEAD":
        current = submit_branch(raw)
    else:
        env = {} if environ is None else environ
        for key in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
            candidate = str(env.get(key) or "").strip()
            if candidate and candidate != "HEAD":
                current = submit_branch(candidate)
                break
    if current is None:
        raise ForgeError(EXIT_CONFIG, "refusing detached HEAD; check out the feature branch")
    if explicit is not None and explicit != current:
        raise ForgeError(
            EXIT_CONFIG,
            f"refusing --head {explicit!r}: checked-out branch is {current!r} "
            "(check runs on this worktree; check out the branch you submit)",
        )
    return current


def resolve_clean_head_sha(
    *,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
) -> str:
    """HEAD sha of a clean tree (untracked included). That sha is what gets pushed."""
    runner = default_git_runner if git_runner is None else git_runner
    dirty = runner(["status", "--porcelain", "--untracked-files=all"], cwd=cwd)
    if (dirty or "").strip():
        raise ForgeError(
            EXIT_CONFIG,
            "refusing dirty worktree (uncommitted or untracked files); "
            "commit or stash first so check sees what is pushed",
        )
    sha = (runner(["rev-parse", "HEAD"], cwd=cwd) or "").strip().lower()
    if not SHA_RE.fullmatch(sha):
        raise ForgeError(EXIT_CONFIG, f"cannot resolve HEAD sha: {sha!r}")
    return sha


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


def intended_title(
    explicit: str | None,
    commit_subject: str | None,
    *,
    scopes: str | list[str] | None = None,
) -> str:
    if explicit is not None:
        return explicit
    if commit_subject:
        code, _, _ = lint_title(commit_subject, scopes=scopes)
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
    sha: str,
    base: str,
    title: str,
    dry_run: bool,
) -> None:
    if dry_run:
        print("dry-run", file=stdout)
    print(f"repo: {repo}", file=stdout)
    print(f"remote: {DEFAULT_REMOTE}", file=stdout)
    print(f"head: {head}", file=stdout)
    print(f"sha: {sha}", file=stdout)
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
            if not isinstance(item, dict):
                continue
            base_obj = item.get("base")
            base_ref = base_obj.get("ref") if isinstance(base_obj, dict) else None
            if base_ref == base:
                existing = item
                break
    if existing and existing.get("number") is not None:
        number = int(existing["number"])
        # Title only: the body is the author's 解说; never overwrite it with the template.
        client.request(
            "PATCH",
            f"/repos/{owner}/{name}/pulls/{number}",
            {"title": title},
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
        assert_submit_allowed(owner, name)
        config_path = None if path is None else Path(path)
        config = load_config(config_path)
        resolved_head = resolve_head(
            head, cwd=cwd, git_runner=git_runner, environ=environ
        )
        assert_head_not_protect(resolved_head, config.protect)
        head_sha = resolve_clean_head_sha(cwd=cwd, git_runner=git_runner)
        locked = {normalize_branch(item) for item in (config.protect or list(DEFAULT_PROTECT))}
        resolved_base = (
            normalize_branch(base)
            if base and base.strip()
            else (config.protect[0] if config.protect else DEFAULT_PROTECT[0])
        )
        if resolved_base not in locked:
            raise ForgeError(
                EXIT_CONFIG,
                f"refusing to submit onto {resolved_base!r}; base must be protect "
                "(squash 封顶; 换底 from main after squash)",
            )
        subject = None if title is not None else resolve_commit_subject(
            cwd=cwd, git_runner=git_runner
        )
        resolved_title = intended_title(title, subject, scopes=config.title_scopes)
        code, message, _parts = lint_title(resolved_title, scopes=config.title_scopes)
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
            sha=head_sha,
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

            def push(remote: str, refspec: str) -> None:
                default_pusher(
                    remote,
                    refspec,
                    cwd=cwd,
                    git_runner=git_runner,
                    token=resolved_token,
                )

        push(DEFAULT_REMOTE, push_refspec(head_sha, resolved_head))
        print(f"pushed {DEFAULT_REMOTE} {resolved_head} ({head_sha[:12]})", file=out)
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
