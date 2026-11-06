"""gitignore-style path matcher shared by deny_paths and docs_sync.paths.

Moved out of forge/check.py unchanged (ADR 0009).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from forge.gitutil import normalize_repo_path

_GLOB_CHARS = frozenset("*?[")


def _glob_regex(pattern: str) -> str:
    """gitignore-style: `**/` = zero or more dirs, `*` / `?` stay inside one segment."""
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if pattern.startswith("**", i):
            at_start = i == 0 or pattern[i - 1] == "/"
            j = i + 2
            if at_start and j < n and pattern[j] == "/":
                out.append("(?:.*/)?")
                i = j + 1
                continue
            if at_start and j == n:
                # "dir/**" also names dir itself (prior behavior); "**" is everything.
                if out and out[-1] == "/":
                    out[-1] = "(?:/.*)?"
                else:
                    out.append(".*")
                i = j
                continue
            out.append("[^/]*")
            i = j
            continue
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        elif ch == "[":
            end = pattern.find("]", i + 2 if pattern[i + 1 : i + 2] in ("!", "^") else i + 1)
            if end == -1:
                out.append(re.escape(ch))
            else:
                body = pattern[i + 1 : end]
                if body[:1] in ("!", "^"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\").replace("[", "\\[") + "]")
                i = end + 1
                continue
        elif ch == "/":
            out.append("/")
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


def path_matches_pattern(path: str, pattern: str) -> bool:
    """One matcher for deny_paths and docs_sync.paths (see docs/forge-config.md).

    Plain path: exact file or directory prefix. Trailing `/`: directory prefix.
    Globs: `**/` matches zero or more directories, `*` and `?` never cross `/`;
    a glob with no `/` matches a basename at any depth. A glob that names a
    directory also covers everything under it.
    """
    rel = normalize_repo_path(path)
    pat = normalize_repo_path(str(pattern)).lstrip("/")
    if pat.endswith("/"):
        pat = pat.rstrip("/")
    if not pat or not rel:
        return False
    if not _GLOB_CHARS.intersection(pat):
        return rel == pat or rel.startswith(pat + "/")
    regex = _glob_regex(pat)
    if "/" not in pat:
        regex = "(?:.*/)?" + regex
    return re.fullmatch(regex + "(?:/.*)?", rel) is not None


def path_is_denied(path: str, deny_paths: Sequence[str]) -> bool:
    return any(path_matches_pattern(path, deny) for deny in deny_paths)


def path_matches_glob(path: str, pattern: str) -> bool:
    return path_matches_pattern(path, pattern)
