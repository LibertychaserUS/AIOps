"""Select active suites for a branch. Pure function. No HTTP. Exit 4 on assert."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, TextIO

from overlay import EXIT_CONTRACT, EXIT_OK, EXIT_SELECT_ASSERT
from overlay.receipt import build_receipt, receipt_filename, write_receipt
from overlay.validate import OverlayConfig, SuiteDoc, validate_root

NEVER_RED_RULE = "never_red_statuses"
KIND_LATER_RULE = "kind_later"
BRANCH_KINDS_RULE = "branch_kinds"
UNKNOWN_BRANCH_RULE = "unknown_branch"
NOT_ACTIVE_RULE = "not_active"


@dataclass(frozen=True)
class Dropped:
    suite_id: str
    status: str
    kind: str
    rule: str
    reason: str | None = None


@dataclass
class Selection:
    selected: list[SuiteDoc]
    dropped: list[Dropped]
    effective_branch: str = ""
    fallback_note: str | None = None


def git_sha(root: Path) -> str:
    env_sha = os.environ.get("GITHUB_SHA", "").strip()
    if env_sha:
        return env_sha
    for cwd in (root, Path.cwd()):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return "unknown"


def default_select_branch(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    for key in ("GITHUB_BASE_REF", "GITHUB_REF_NAME"):
        value = (env.get(key) or "").strip()
        if value:
            return value
    return "main"


def resolve_branch_policy(
    config: OverlayConfig, branch: str
) -> tuple[str, frozenset[str] | None, str | None]:
    """Look up overlay.yaml branches.<name>; unknown falls back to default then main."""
    if branch in config.branches:
        return branch, config.branches[branch], None
    if "default" in config.branches:
        return (
            "default",
            config.branches["default"],
            f"unknown branch {branch!r}; falling back to branches.default",
        )
    if "main" in config.branches:
        return (
            "main",
            config.branches["main"],
            f"unknown branch {branch!r}; falling back to main",
        )
    return branch, None, f"unknown branch {branch!r}; no branches.default or main"


def _effective_status(suite: SuiteDoc) -> str:
    return suite.status.strip() if suite.status.strip() else "active"


def select_suites(suites: list[SuiteDoc], config: OverlayConfig, branch: str) -> Selection:
    selected: list[SuiteDoc] = []
    dropped: list[Dropped] = []
    effective, branch_kinds, note = resolve_branch_policy(config, branch)
    ordered = sorted(suites, key=lambda item: item.suite_id)
    for suite in ordered:
        status = _effective_status(suite)
        if status in config.never_red_statuses:
            dropped.append(
                Dropped(
                    suite.suite_id,
                    status,
                    suite.kind,
                    NEVER_RED_RULE,
                    reason=suite.blocked_reason,
                )
            )
            continue
        later_key = None
        if config.kinds.get(suite.kind) == "later":
            later_key = suite.kind
        elif config.kinds.get(suite.subject) == "later" or suite.subject == "agent":
            later_key = suite.subject
        if later_key is not None:
            dropped.append(Dropped(suite.suite_id, status, suite.kind, KIND_LATER_RULE))
            continue
        if branch_kinds is None:
            dropped.append(Dropped(suite.suite_id, status, suite.kind, UNKNOWN_BRANCH_RULE))
            continue
        if suite.kind not in branch_kinds:
            dropped.append(Dropped(suite.suite_id, status, suite.kind, BRANCH_KINDS_RULE))
            continue
        if status != "active":
            dropped.append(Dropped(suite.suite_id, status, suite.kind, NOT_ACTIVE_RULE))
            continue
        selected.append(suite)
    return Selection(
        selected=selected,
        dropped=dropped,
        effective_branch=effective,
        fallback_note=note,
    )


def assert_selection(selection: Selection) -> list[str]:
    bad = [item.suite_id for item in selection.selected if item.status in {"draft", "blocked"}]
    if not bad:
        return []
    return [
        f"select assertion: draft/blocked present in selected: {', '.join(bad)}"
    ]


def _first_function_meta(suite: SuiteDoc) -> tuple[str | None, str | None]:
    if suite.function_ids:
        fid = suite.function_ids[0]
        level = None
        for item in suite.trace_items:
            if item.get("function_id") == fid:
                level = item.get("level")
                break
        return fid, level if isinstance(level, str) else None
    return None, None


def selection_events(selection: Selection) -> list[dict[str, object]]:
    events: list[dict[str, object]] = [{"type": "validated"}]
    for suite in selection.selected:
        event: dict[str, object] = {
            "type": "selected",
            "suite": suite.suite_id,
            "status": _effective_status(suite),
            "kind": suite.kind,
        }
        function_id, level = _first_function_meta(suite)
        if function_id:
            event["function_id"] = function_id
        if level:
            event["level"] = level
        events.append(event)
    for item in selection.dropped:
        event = {
            "type": "dropped",
            "suite": item.suite_id,
            "status": item.status,
            "rule": item.rule,
        }
        if item.reason:
            event["reason"] = item.reason
        events.append(event)
    return events


def selection_evidence(suites: list[SuiteDoc]) -> list[dict[str, object]]:
    return [
        {
            "type": "contract",
            "rule": "blocked requires blocked_reason with a link or register id",
        }
    ]


def run_select(
    root: Path,
    branch: str,
    write_receipt_dir: Path | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    issues, config, _inboxes, suites = validate_root(root)
    if issues or config is None:
        for issue in issues:
            print(issue, file=err)
        print("overlay select: validate failed", file=err)
        return EXIT_CONTRACT

    selection = select_suites(suites, config, branch)
    if selection.fallback_note:
        print(f"overlay select: {selection.fallback_note}", file=err)
    assert_errors = assert_selection(selection)
    if assert_errors:
        for message in assert_errors:
            print(message, file=err)
        return EXIT_SELECT_ASSERT

    if write_receipt_dir is not None:
        sha = git_sha(root)
        receipt = build_receipt(
            wrote_by="select",
            git_sha=sha,
            branch=branch,
            events=selection_events(selection),
            evidence=selection_evidence(suites),
        )
        run_id = os.environ.get("GITHUB_RUN_ID", "").strip() or None
        filename = receipt_filename(branch, sha, run_id)
        path = write_receipt(write_receipt_dir, receipt, filename)
        print(f"overlay select: wrote {path.as_posix()}", file=err)

    for suite in selection.selected:
        print(suite.suite_id, file=out)
    for item in selection.dropped:
        extra = f" reason={item.reason}" if item.reason else ""
        print(
            f"overlay select: dropped {item.suite_id} status={item.status} rule={item.rule}{extra}",
            file=err,
        )
    print(
        f"overlay select: selected={len(selection.selected)} dropped={len(selection.dropped)}",
        file=err,
    )
    return EXIT_OK
