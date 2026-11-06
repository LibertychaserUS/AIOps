"""One copy of the git helpers forge check / status / ci-select / title share.

Moved here unchanged (ADR 0009); each module re-exports the names it owned.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path


class GitUnavailable(Exception):
    """git is not on PATH: a diff gate cannot see anything, so it fails."""


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # quotePath=false: a quoted "secret/\345..." would never match deny_paths.
    try:
        return subprocess.run(
            ["git", "-C", str(root), "-c", "core.quotePath=false", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GitUnavailable(f"cannot run git ({exc})") from exc


_git = run_git


def git_paths(root: Path, *args: str) -> list[str] | None:
    """NUL-separated path listing (-z): no quoting, no newline ambiguity."""
    proc = run_git(root, args[0], "-z", *args[1:])
    if proc.returncode != 0:
        return None
    return [normalize_repo_path(item) for item in proc.stdout.split("\0") if item.strip()]


_git_paths = git_paths


def git_log(root: Path | str, *args: str) -> str | None:
    """`git log` isolated from the developer's global config (signers, hooks)."""
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    proc = subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", "log", *args],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def head_is_merge(root: Path | str | None) -> bool:
    """True when HEAD has two or more parents (a base-branch merge, not a change)."""
    if root is None:
        return False
    parents = git_log(root, "-1", "--format=%P")
    return bool(parents) and len(parents.split()) >= 2


def is_git_work_tree(root: Path) -> bool:
    proc = run_git(root, "rev-parse", "--is-inside-work-tree")
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def current_branch(root: Path) -> str | None:
    proc = run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if proc.returncode != 0:
        return None
    name = proc.stdout.strip()
    if not name or name == "HEAD":
        return None
    return name


def resolve_protect_ref(
    root: Path,
    protect: Sequence[str],
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """The PR base is the remote protect branch; a stale local copy must not win.

    Last resort is the Actions PR base (origin/$GITHUB_BASE_REF). None means the
    diff gates cannot see the base; callers fail closed instead of diffing HEAD.
    """
    for name in protect:
        for candidate in (
            f"refs/remotes/origin/{name}",
            f"origin/{name}",
            f"refs/heads/{name}",
            name,
        ):
            proc = run_git(root, "rev-parse", "--verify", "--quiet", candidate)
            if proc.returncode == 0:
                return candidate
    env = os.environ if environ is None else environ
    base = (env.get("GITHUB_BASE_REF") or "").strip()
    if base:
        candidate = f"refs/remotes/origin/{base}"
        if run_git(root, "rev-parse", "--verify", "--quiet", candidate).returncode == 0:
            return candidate
    return None


def no_base_detail(protect: Sequence[str]) -> str:
    name = protect[0] if protect else "main"
    return (
        f"cannot see the base: no origin/{name} (or local {name}); "
        f"run git fetch origin {name} and re-run"
    )


def resolve_base_commit(
    root: Path,
    protect: Sequence[str],
    environ: Mapping[str, str] | None = None,
) -> str | None:
    base_ref = resolve_protect_ref(root, protect, environ)
    if not base_ref:
        return None
    return merge_base_or_ref(root, base_ref)


def merge_base_or_ref(root: Path, base_ref: str) -> str:
    """merge-base(HEAD, base_ref), or base_ref itself when git cannot compute one."""
    merge = run_git(root, "merge-base", "HEAD", base_ref)
    if merge.returncode == 0 and merge.stdout.strip():
        return merge.stdout.strip()
    return base_ref


def normalize_repo_path(path: str) -> str:
    rel = path.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def list_changed_paths(root: Path, base_ref: str | None) -> list[str] | None:
    """Changed paths under root vs protect merge-base (or HEAD), relative to root.

    Union of committed (base..HEAD), index and worktree: a staged revert must
    not hide a committed change that the push still carries.
    --relative keeps a monorepo product's deny_paths meaningful when --root is a
    subdirectory; untracked files from ls-files are already cwd-relative.
    None if not a git work tree.
    """
    if not is_git_work_tree(root):
        return None
    paths: set[str] = set()
    diff = ("diff", "--name-only", "--no-renames", "--relative")
    if base_ref:
        base = merge_base_or_ref(root, base_ref)
        listings = ((*diff, base, "HEAD"), (*diff, base), (*diff, "--cached", base))
    else:
        listings = ((*diff, "HEAD"), (*diff, "--cached"))
    for args in (*listings, ("ls-files", "--others", "--exclude-standard")):
        found = git_paths(root, *args)
        if found is not None:
            paths.update(found)
    return sorted(p for p in paths if p)


def matching_agent_prefix(branch: str | None, prefixes: Sequence[str]) -> str | None:
    if not branch:
        return None
    for prefix in prefixes:
        if branch.startswith(prefix):
            return prefix
    return None


def resolve_branch(
    root: Path,
    environ: Mapping[str, str] | None = None,
    head_branch: str | None = None,
) -> str | None:
    """Explicit head (submit --head), branch name locally, or the CI PR head.

    None when nothing names the branch; suite_guard then treats it as an agent.
    """
    if head_branch and head_branch.strip():
        return head_branch.strip()
    name = current_branch(root)
    if name:
        return name
    env = os.environ if environ is None else environ
    for key in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
        value = (env.get(key) or "").strip()
        if value:
            return value
    return None
