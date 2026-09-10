"""Submit credential is FORGE_SUBMIT_TOKEN only.

Ambient gh auth, GH_TOKEN, git extraheader, GITHUB_TOKEN, and
FORGE_GITHUB_TOKEN are not enough. Never return or print the secret value.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

from forge import SUBMIT_TOKEN_ENV

_SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"(?i)(authorization:\s*\S+\s+)\S+"),
)


def redact_secrets(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            out = pattern.sub(r"\1REDACTED", out)
        else:
            out = pattern.sub("REDACTED", out)
    return out


@dataclass(frozen=True)
class WriteCredential:
    present: bool
    source: str
    detail: str

    def __repr__(self) -> str:
        return f"WriteCredential(present={self.present!r}, source={self.source!r})"


MISSING = WriteCredential(
    present=False,
    source="none",
    detail=f"missing {SUBMIT_TOKEN_ENV}",
)

MISSING_MESSAGE = (
    f"missing {SUBMIT_TOKEN_ENV}\n"
    "Agent/local forge submit requires this named GitHub secret "
    "(PAT / fine-grained / GitHub App token).\n"
    "Ambient gh auth, GH_TOKEN, git extraheader, GITHUB_TOKEN, and "
    "FORGE_GITHUB_TOKEN are not enough.\n"
    "Ops merge uses other permissions. Never print the token."
)


def probe_write_credential(
    *,
    environ: Mapping[str, str] | os._Environ[str] | None = None,
    cwd: object = None,
    host: str | None = None,
    gh_status: object = None,
    git_extraheader: object = None,
) -> WriteCredential:
    """Fail-closed: only FORGE_SUBMIT_TOKEN counts. Extra kwargs ignored."""
    del cwd, host, gh_status, git_extraheader
    env = os.environ if environ is None else environ
    raw = env.get(SUBMIT_TOKEN_ENV)
    if raw is not None and str(raw).strip():
        return WriteCredential(
            present=True,
            source=SUBMIT_TOKEN_ENV,
            detail="named submit secret (value not shown)",
        )
    return MISSING
