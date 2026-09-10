"""Select armed suites for a branch. Pure function. No HTTP. Exit 4 on assert."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from overlay import EXIT_CONTRACT, EXIT_OK, EXIT_SELECT_ASSERT
from overlay.receipt import build_receipt, receipt_filename, write_receipt
from overlay.validate import OverlayConfig, SuiteDoc, validate_root

NEVER_RED_RULE = "never_red_statuses"
KIND_LATER_RULE = "kind_later"
BRANCH_KINDS_RULE = "branch_kinds"
UNKNOWN_BRANCH_RULE = "unknown_branch"
NOT_ARMED_RULE = "not_armed"


@dataclass(frozen=True)
class Dropped:
    suite_id: str
    status: str
    kind: str
    rule: str


@dataclass
class Selection:
    selected: list[SuiteDoc]
    dropped: list[Dropped]


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


def select_suites(suites: list[SuiteDoc], config: OverlayConfig, branch: str) -> Selection:
    selected: list[SuiteDoc] = []
    dropped: list[Dropped] = []
    branch_kinds = config.branches.get(branch)
    ordered = sorted(suites, key=lambda item: item.suite_id)
    for suite in ordered:
        if suite.status in config.never_red_statuses:
            dropped.append(Dropped(suite.suite_id, suite.status, suite.kind, NEVER_RED_RULE))
            continue
        later_key = None
        if config.kinds.get(suite.kind) == "later":
            later_key = suite.kind
        elif config.kinds.get(suite.subject) == "later" or suite.subject == "agent":
            later_key = suite.subject
        if later_key is not None:
            dropped.append(Dropped(suite.suite_id, suite.status, suite.kind, KIND_LATER_RULE))
            continue
        if branch_kinds is None:
            dropped.append(Dropped(suite.suite_id, suite.status, suite.kind, UNKNOWN_BRANCH_RULE))
            continue
        if suite.kind not in branch_kinds:
            dropped.append(Dropped(suite.suite_id, suite.status, suite.kind, BRANCH_KINDS_RULE))
            continue
        if suite.status != "armed":
            dropped.append(Dropped(suite.suite_id, suite.status, suite.kind, NOT_ARMED_RULE))
            continue
        selected.append(suite)
    return Selection(selected=selected, dropped=dropped)


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
            "status": suite.status,
            "kind": suite.kind,
        }
        function_id, level = _first_function_meta(suite)
        if function_id:
            event["function_id"] = function_id
        if level:
            event["level"] = level
        events.append(event)
    for item in selection.dropped:
        events.append(
            {
                "type": "dropped",
                "suite": item.suite_id,
                "status": item.status,
                "rule": item.rule,
            }
        )
    return events


def selection_evidence(suites: list[SuiteDoc]) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = [
        {
            "type": "contract",
            "rule": "missing reviewed_by on blocked|armed is overlay-red",
        }
    ]
    for suite in sorted(suites, key=lambda item: item.suite_id):
        if suite.reviewed_by:
            evidence.append(
                {
                    "type": "human-review",
                    "suite": suite.suite_id,
                    "reviewed_by": suite.reviewed_by,
                }
            )
    return evidence


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
        print(
            f"overlay select: dropped {item.suite_id} status={item.status} rule={item.rule}",
            file=err,
        )
    print(
        f"overlay select: selected={len(selection.selected)} dropped={len(selection.dropped)}",
        file=err,
    )
    return EXIT_OK
