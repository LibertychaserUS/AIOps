"""Human review writes. Agent branches cannot set or clear blocked."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import TextIO

from overlay import EXIT_CONTRACT, EXIT_OK
from overlay.validate import BLOCKED_REASON_REF_RE

KEY_RE = re.compile(r"^(\s*)([A-Za-z0-9_]+)\s*:(.*)$")
MULTILINE_INDICATORS = frozenset({">", "|", ">-", "|-", ">+", "|+"})


def yaml_scalar(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:#@+-]+", value):
        return value
    return json.dumps(value, ensure_ascii=False)


def rewrite_status(text: str, status: str, blocked_reason: str | None) -> str:
    """Replace status and blocked_reason. Keep every other line."""
    had_nl = text.endswith("\n")
    reason_line = (
        "blocked_reason: null"
        if blocked_reason is None
        else f"blocked_reason: {yaml_scalar(blocked_reason)}"
    )
    out: list[str] = []
    skip_indent: int | None = None
    saw_status = False
    saw_reason = False
    for line in text.splitlines():
        if skip_indent is not None:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent > skip_indent:
                continue
            skip_indent = None
        match = KEY_RE.match(line)
        if match is not None and match.group(1) == "":
            key, rest = match.group(2), match.group(3)
            if key == "status":
                saw_status = True
                out.append(f"status: {status}")
                continue
            if key == "blocked_reason":
                saw_reason = True
                token = rest.strip()
                if token in MULTILINE_INDICATORS or token == "":
                    skip_indent = 0
                out.append(reason_line)
                continue
        out.append(line)
    if not saw_status:
        out.append(f"status: {status}")
    if not saw_reason:
        out.append(reason_line)
    result = "\n".join(out)
    if had_nl or not result.endswith("\n"):
        result += "\n"
    return result


def _refuse_agent_or_missing_forge(root: Path, err: TextIO) -> str | None:
    """None when a human branch may write. Otherwise the refusal message."""
    forge_yaml = root / "forge.yaml"
    if not forge_yaml.is_file():
        return "overlay review: no forge.yaml; refusing writes"
    try:
        from forge.apply import ForgeError, load_config
        from forge.check import matching_agent_prefix, resolve_branch
    except ImportError:
        return "overlay review: forge is unavailable; refusing writes"
    try:
        config = load_config(forge_yaml)
    except ForgeError as exc:
        return f"overlay review: {exc.message}"
    branch = resolve_branch(root)
    if not branch:
        return "overlay review: cannot resolve git branch; refusing writes"
    prefix = matching_agent_prefix(branch, config.agent_branch_prefixes)
    if prefix:
        return (
            "overlay review: refusing write on agent branch "
            f"{branch} (prefix {prefix}); agents must not set or clear blocked"
        )
    return None


def run_review(
    *,
    root: Path | None = None,
    i_am: str | None,
    suite: str | None = None,
    status: str | None = None,
    reason: str | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    err = sys.stderr if stderr is None else stderr
    out = sys.stdout if stdout is None else stdout
    overlay_root = (Path.cwd() if root is None else root).resolve()
    if not (i_am or "").strip():
        print("overlay review refuses without --i-am HUMAN", file=err)
        return EXIT_CONTRACT
    if not (suite or "").strip() or not (status or "").strip():
        print("overlay review: --suite and --status are required", file=err)
        return EXIT_CONTRACT
    if status not in {"active", "blocked"}:
        print(f"overlay review: illegal status {status!r}", file=err)
        return EXIT_CONTRACT
    reason_text = (reason or "").strip()
    if not reason_text:
        print("overlay review: --reason is required", file=err)
        return EXIT_CONTRACT
    if status == "blocked" and BLOCKED_REASON_REF_RE.search(reason_text) is None:
        print(
            "overlay review: blocked requires --reason with a link (http(s)://) "
            "or a register id (OF-12, #123)",
            file=err,
        )
        return EXIT_CONTRACT
    refusal = _refuse_agent_or_missing_forge(overlay_root, err)
    if refusal:
        print(refusal, file=err)
        return EXIT_CONTRACT
    suite_id = suite.strip()
    path = overlay_root / "suites" / suite_id / "suite.yaml"
    if not path.is_file():
        print(f"overlay review: missing {path.as_posix()}", file=err)
        return EXIT_CONTRACT
    original = path.read_text(encoding="utf-8")
    blocked_reason = reason_text if status == "blocked" else None
    updated = rewrite_status(original, status, blocked_reason)
    path.write_text(updated, encoding="utf-8")
    print(
        f"overlay review: i-am={i_am.strip()} suite={suite_id} status={status}",
        file=out,
    )
    return EXIT_OK
