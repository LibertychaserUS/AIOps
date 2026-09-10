"""Detect a host-injected GitHub write credential. Forge does not store secrets.

Presence only. Never return, log, or print the secret value.
See docs/submit-credential.md.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOST = "github.com"

_SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"(?i)(authorization:\s*\S+\s+)\S+"),
)


def redact_secrets(text: str) -> str:
    """Strip token-shaped strings before any message is printed."""
    out = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            out = pattern.sub(r"\1REDACTED", out)
        else:
            out = pattern.sub("REDACTED", out)
    return out


@dataclass(frozen=True)
class WriteCredential:
    """Host-injected write login. `source` is a name, never a secret."""

    present: bool
    source: str  # gh-login | GH_TOKEN | git-extraheader | none
    detail: str

    def __repr__(self) -> str:
        return f"WriteCredential(present={self.present!r}, source={self.source!r})"


MISSING = WriteCredential(
    present=False,
    source="none",
    detail="no usable GitHub write credential",
)

MISSING_IN_ACTIONS = WriteCredential(
    present=False,
    source="none",
    detail="CI GITHUB_TOKEN is check+merge lock, not 代推",
)

MISSING_MESSAGE = (
    "no usable GitHub write credential\n"
    "Forge does not store secrets. Host must inject a GitHub write login:\n"
    "  human:  gh auth login  (~/.config/gh or OS keychain; not the git repo)\n"
    "  agent:  Cursor/platform GH_TOKEN or git https extraheader (runtime only)\n"
    "  CI:     do not forge submit; GITHUB_TOKEN is check+merge lock\n"
    "Do not paste a PAT into chat."
)


def in_github_actions(environ: Mapping[str, str] | os._Environ[str] | None) -> bool:
    env = os.environ if environ is None else environ
    return str(env.get("GITHUB_ACTIONS", "")).strip().lower() == "true"


def _env_present(environ: Mapping[str, str] | os._Environ[str], key: str) -> bool:
    return bool(str(environ.get(key, "")).strip())


def _run_quiet(
    argv: list[str],
    *,
    cwd: Path | str | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
) -> int:
    env = dict(os.environ if environ is None else environ)
    env.pop("GH_DEBUG", None)
    env.pop("GH_TRACE", None)
    result = subprocess.run(
        argv,
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return int(result.returncode)


def default_gh_logged_in(
    *,
    host: str = DEFAULT_HOST,
    cwd: Path | str | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
) -> bool:
    """True when `gh auth status` is authenticated. Discard stdout (may mention a token)."""
    return (
        _run_quiet(
            ["gh", "auth", "status", "--hostname", host],
            cwd=cwd,
            environ=environ,
        )
        == 0
    )


def default_git_extraheader_present(
    *,
    host: str = DEFAULT_HOST,
    cwd: Path | str | None = None,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
) -> bool:
    """True when git has an https extraheader for this host. Discard the value (it is the secret)."""
    keys = (
        f"http.https://{host}/.extraheader",
        f"http.https://{host}.extraheader",
    )
    for key in keys:
        code = _run_quiet(["git", "config", "--get", key], cwd=cwd, environ=environ)
        if code == 0:
            return True
    return False


def probe_write_credential(
    *,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
    cwd: Path | str | None = None,
    host: str = DEFAULT_HOST,
    gh_status: Callable[[], bool] | None = None,
    git_extraheader: Callable[[], bool] | None = None,
) -> WriteCredential:
    """Fail-closed presence check. Never copies a token onto this object."""
    env: Mapping[str, str] | os._Environ[str] = os.environ if environ is None else environ
    if in_github_actions(env):
        return MISSING_IN_ACTIONS
    if _env_present(env, "GH_TOKEN"):
        return WriteCredential(
            present=True,
            source="GH_TOKEN",
            detail="host-injected GH_TOKEN (value not shown)",
        )
    extra = git_extraheader if git_extraheader is not None else (
        lambda: default_git_extraheader_present(host=host, cwd=cwd, environ=env)
    )
    if extra():
        return WriteCredential(
            present=True,
            source="git-extraheader",
            detail="git https extraheader (value not shown)",
        )
    logged_in = gh_status if gh_status is not None else (
        lambda: default_gh_logged_in(host=host, cwd=cwd, environ=env)
    )
    if logged_in():
        return WriteCredential(
            present=True,
            source="gh-login",
            detail="gh auth login / credential store",
        )
    return MISSING
