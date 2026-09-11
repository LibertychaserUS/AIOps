"""Open or update a promote PR. Never merges.

Needs FORGE_SUBMIT_TOKEN (same secret as submit). If an open PR already
exists with head=from and base=to, PATCH title/body; otherwise POST a
non-draft PR. Body uses the six 解说规格 headings; 做了什么 is filled
from `git log to..from --format=- %s`.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from forge import EXIT_AUTH, EXIT_CONFIG, EXIT_OK
from forge.apply import (
    DEFAULT_API,
    ForgeError,
    GitHubClient,
    UrlOpen,
    load_config,
    normalize_branch,
    parse_repo,
)
from forge.submit import (
    BODY_HEADINGS,
    MISSING_SUBMIT_TOKEN,
    REQUIRE_SUBMIT_TOKEN,
    GitRunner,
    default_git_runner,
    pr_body,
    resolve_submit_token,
)
from forge.title import lint_title


def promote_scope(scopes: str | list[str] | None) -> str:
    if isinstance(scopes, list) and scopes:
        return scopes[0]
    return "release/agent"


def promote_title(from_branch: str, to_branch: str, short_sha: str, scopes: str | list[str] | None) -> str:
    scope = promote_scope(scopes)
    return f"chore({scope}): promote {from_branch} → {to_branch} ({short_sha})"


def promote_body(commits: Sequence[str]) -> str:
    what = "\n".join(commits) if commits else "- (no commits)"
    sections = {
        "做了什么": what,
        "为什么": "promote protected branch",
        "动了哪些门": "none (promote PR)",
        "怎么验": "required checks on the target branch",
        "不做什么": "does not merge",
        "分工": "human approval on the target branch",
    }
    parts: list[str] = []
    for heading in BODY_HEADINGS:
        parts.append(f"## {heading}\n\n{sections.get(heading, '')}\n")
    return "\n".join(parts)


def _open_or_update_promote(
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
        f"/repos/{owner}/{name}/pulls?state=open&head={owner}:{head}&base={base}&per_page=10",
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
            "draft": False,
        },
    )
    if not isinstance(created, dict) or created.get("number") is None:
        raise ForgeError(EXIT_CONFIG, "GitHub API returned a non-object create result")
    return "opened", int(created["number"])


def run_promote(
    *,
    repo: str,
    from_branch: str,
    to_branch: str,
    dry_run: bool = False,
    path: Path | str | None = None,
    token: str | None = None,
    urlopen: UrlOpen | None = None,
    base_url: str = DEFAULT_API,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
    cwd: Path | str | None = None,
    git_runner: GitRunner | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    try:
        owner, name = parse_repo(repo)
        config_path = None if path is None else Path(path)
        config = load_config(config_path)
        source = normalize_branch(from_branch)
        target = normalize_branch(to_branch)
        locked = {normalize_branch(item) for item in config.protect}
        if target not in locked:
            raise ForgeError(EXIT_CONFIG, f"refusing to promote onto {target!r}; --to must be protect")
        rule = config.rule_for(target)
        if rule.promote_from and rule.promote_from != source:
            raise ForgeError(
                EXIT_CONFIG,
                f"refusing promote {source!r} → {target!r}; branches.{target}.promote_from is {rule.promote_from!r}",
            )
        runner = default_git_runner if git_runner is None else git_runner
        short_sha = runner(["rev-parse", "--short", source], cwd=cwd) or "unknown"
        log = runner(["log", f"{target}..{source}", "--format=- %s"], cwd=cwd)
        commits = [line for line in (log or "").splitlines() if line.strip()]
        title = promote_title(source, target, short_sha, config.title_scopes)
        code, message, _ = lint_title(title, scopes=config.title_scopes)
        if code != EXIT_OK:
            raise ForgeError(EXIT_CONFIG, message)
        body = promote_body(commits)
        if dry_run:
            print("dry-run", file=out)
        print(f"repo: {owner}/{name}", file=out)
        print(f"from: {source}", file=out)
        print(f"to: {target}", file=out)
        print(f"title: {title}", file=out)
        print("body headings:", file=out)
        for heading in BODY_HEADINGS:
            print(f"  {heading}", file=out)
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
        client = GitHubClient(resolved_token, urlopen=urlopen, base_url=base_url)
        action, number = _open_or_update_promote(
            client,
            owner=owner,
            name=name,
            head=source,
            base=target,
            title=title,
            body=body,
        )
        print(f"{action} promote PR #{number}", file=out)
        return EXIT_OK
    except ForgeError as exc:
        print(exc.message, file=err)
        return exc.code
