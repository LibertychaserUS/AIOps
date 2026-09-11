"""Rewrite overlay-suite/v1 files to overlay-suite/v2. Line-preserving. No YAML dump."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TextIO

import yaml

from overlay import EXIT_OK
from overlay.validate import is_blank, iter_suite_paths

SUITE_SCHEMA_V2 = "overlay-suite/v2"
REMOVED_KEYS = frozenset({"reviewed_by", "reviewed_at", "armed_reason"})
OLD_STATUSES = frozenset({"draft", "armed"})
MULTILINE_INDICATORS = frozenset({">", "|", ">-", "|-", ">+", "|+"})
KEY_RE = re.compile(r"^(\s*)([A-Za-z0-9_]+)\s*:(.*)$")
DRAFT_ITEM_RE = re.compile(r"^(\s*)-\s*draft\s*$")
NEVER_RED_RE = re.compile(r"^(\s*)never_red_statuses\s*:\s*(.*)$")


def _blocked_missing_reason(text: str) -> bool:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    if str(data.get("status") or "").strip() != "blocked":
        return False
    return is_blank(data.get("blocked_reason"))


def rewrite_suite_text(text: str) -> str:
    """Map draft/armed → active, drop removed keys, set schema v2. Keep other lines."""
    had_nl = text.endswith("\n")
    lines = text.splitlines()
    out: list[str] = []
    skip_indent: int | None = None
    saw_schema = False
    for line in lines:
        if skip_indent is not None:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent > skip_indent:
                continue
            skip_indent = None
        match = KEY_RE.match(line)
        if match is not None:
            indent, key, rest = match.group(1), match.group(2), match.group(3)
            if key == "schema":
                saw_schema = True
                if rest.strip() != SUITE_SCHEMA_V2:
                    out.append(f"{indent}schema: {SUITE_SCHEMA_V2}")
                    continue
            if key in REMOVED_KEYS:
                token = rest.strip()
                if token in MULTILINE_INDICATORS or token == "":
                    skip_indent = len(indent)
                continue
            if key == "status" and rest.strip() in OLD_STATUSES:
                out.append(f"{indent}status: active")
                continue
        out.append(line)
    if not saw_schema:
        out.insert(0, f"schema: {SUITE_SCHEMA_V2}")
    result = "\n".join(out)
    if had_nl:
        result += "\n"
    return result


def rewrite_overlay_yaml(text: str) -> str:
    """Drop never_red_statuses: draft while keeping the rest of the file."""
    had_nl = text.endswith("\n")
    lines = text.splitlines()
    out: list[str] = []
    in_never = False
    never_indent = 0
    for line in lines:
        header = NEVER_RED_RE.match(line)
        if header is not None:
            in_never = True
            never_indent = len(header.group(1))
            rest = header.group(2).strip()
            if rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1]
                items = [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
                kept = [item for item in items if item != "draft"]
                if "blocked" not in kept:
                    kept.append("blocked")
                out.append(f"{header.group(1)}never_red_statuses: [{', '.join(kept)}]")
                in_never = False
                continue
            out.append(line)
            continue
        if in_never:
            if not line.strip():
                out.append(line)
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent <= never_indent and not line.lstrip().startswith("-"):
                in_never = False
                out.append(line)
                continue
            if DRAFT_ITEM_RE.match(line):
                continue
        out.append(line)
    result = "\n".join(out)
    if had_nl:
        result += "\n"
    return result


def run_migrate(
    root: Path,
    *,
    dry_run: bool = False,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    root = root.resolve()
    prefix = "overlay migrate (dry-run)" if dry_run else "overlay migrate"
    rewritten = 0
    skipped = 0

    overlay_path = root / "overlay.yaml"
    if overlay_path.is_file():
        old = overlay_path.read_text(encoding="utf-8")
        new = rewrite_overlay_yaml(old)
        if new != old:
            print(f"{prefix}: overlay.yaml never_red_statuses", file=out)
            if not dry_run:
                overlay_path.write_text(new, encoding="utf-8")
            rewritten += 1

    for path in iter_suite_paths(root):
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        text = path.read_text(encoding="utf-8")
        if _blocked_missing_reason(text):
            print(
                f"{prefix}: skip {rel} (blocked missing blocked_reason; 待办)",
                file=err,
            )
            skipped += 1
            continue
        new = rewrite_suite_text(text)
        if new == text:
            continue
        print(f"{prefix}: rewrite {rel}", file=out)
        if not dry_run:
            path.write_text(new, encoding="utf-8")
        rewritten += 1

    print(f"{prefix}: rewritten={rewritten} skipped={skipped}", file=out)
    return EXIT_OK
