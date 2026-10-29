"""Secret redaction for Forge error output.

The submit credential is FORGE_SUBMIT_TOKEN only (see forge/submit.py and
docs/submit-credential.md). Nothing here reads it; this module makes sure a
failing git / API call cannot echo it (or any other GitHub token) back.
"""

from __future__ import annotations

import re

REDACTED = "REDACTED"

# Order matters: the header / userinfo patterns keep their prefix, the bare
# token patterns replace the whole token.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # `AUTHORIZATION: bearer <token>` / `authorization: basic <base64>` (any scheme).
    (re.compile(r"(?i)(authorization:\s*\S+\s+)\S+"), rf"\g<1>{REDACTED}"),
    # `https://x-access-token:ghp_...@github.com/...` — the password part of a URL userinfo.
    (re.compile(r"(://[^/\s@:]+:)[^@/\s]+@"), rf"\g<1>{REDACTED}@"),
    # Classic / OAuth / user-to-server / server-to-server / refresh tokens.
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]+"), REDACTED),
    # Fine-grained personal access tokens.
    (re.compile(r"github_pat_[A-Za-z0-9_]+"), REDACTED),
)


def redact_secrets(text: str) -> str:
    """Replace GitHub tokens, Authorization header values and URL passwords."""
    out = text
    for pattern, replacement in _SECRET_PATTERNS:
        out = pattern.sub(replacement, out)
    return out
