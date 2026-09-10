"""Read-only check: is forge-protected-default installed?"""

from __future__ import annotations

import os
import sys
from typing import Any

from forge import EXIT_AUTH, EXIT_OK, RULESET_NAME
from forge.apply import (
    DEFAULT_API,
    ForgeError,
    GitHubClient,
    UrlOpen,
    find_named_ruleset,
    parse_repo,
    protect_from_ruleset,
    resolve_token,
)


def run_status(
    *,
    repo: str,
    token: str | None = None,
    urlopen: UrlOpen | None = None,
    base_url: str = DEFAULT_API,
    stdout: Any = None,
    stderr: Any = None,
    environ: dict[str, str] | os._Environ[str] | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    try:
        owner, name = parse_repo(repo)
        resolved = token if token is not None else resolve_token(environ)
        if not resolved:
            print("missing FORGE_GITHUB_TOKEN or GITHUB_TOKEN", file=err)
            return EXIT_AUTH
        client = GitHubClient(resolved, urlopen=urlopen, base_url=base_url)
        existing = find_named_ruleset(client.list_rulesets(owner, name))
        if not existing:
            print("installed: no", file=out)
            print(f"name: {RULESET_NAME}", file=out)
            return EXIT_OK
        detail = existing
        ruleset_id = existing.get("id")
        if ruleset_id is not None:
            try:
                detail = client.get_ruleset(owner, name, int(ruleset_id))
            except ForgeError:
                detail = existing
        branches = protect_from_ruleset(detail) or protect_from_ruleset(existing)
        print("installed: yes", file=out)
        print(f"id: {detail.get('id', ruleset_id)}", file=out)
        print(f"name: {detail.get('name', RULESET_NAME)}", file=out)
        print(f"protect: {', '.join(branches) if branches else '(unknown)'}", file=out)
        return EXIT_OK
    except ForgeError as exc:
        print(exc.message, file=err)
        return exc.code
