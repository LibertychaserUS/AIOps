"""Guarded text-level YAML edits.

review and migrate rewrite suite.yaml line by line to keep comments and order.
Before such a rewrite lands, the parsed documents must differ only in the keys
the command meant to touch, and the file is replaced atomically.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

_MISSING = object()


def atomic_write_text(path: Path, text: str) -> None:
    """Write via a temp file in the same directory, then rename over path."""
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def changed_top_level_keys(before: str, after: str) -> set[str] | None:
    """Top-level keys whose parsed value differs. None when either side is not a mapping."""
    try:
        old = yaml.safe_load(before)
        new = yaml.safe_load(after)
    except yaml.YAMLError:
        return None
    if not isinstance(old, dict) or not isinstance(new, dict):
        return None
    return {key for key in set(old) | set(new) if old.get(key, _MISSING) != new.get(key, _MISSING)}


def unexpected_changes(before: str, after: str, allowed: frozenset[str]) -> str | None:
    """A one-line refusal reason, or None when the edit is confined to allowed keys."""
    changed = changed_top_level_keys(before, after)
    if changed is None:
        return "file does not parse as a YAML mapping before or after the edit"
    extra = sorted(changed - allowed)
    if extra:
        return f"edit would also change {extra}"
    return None
