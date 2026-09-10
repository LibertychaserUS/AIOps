"""Run armed suite product_command. No model. No foreign product checkout."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TextIO

from overlay import EXIT_CONTRACT, EXIT_OK, EXIT_RUN, EXIT_SELECT_ASSERT
from overlay.receipt import build_receipt, receipt_filename, write_receipt
from overlay.select import (
    assert_selection,
    git_sha,
    select_suites,
    selection_events,
    selection_evidence,
)
from overlay.validate import OverlayConfig, SuiteDoc, forbid_host_url_hits, validate_root

DEFAULT_TIMEOUT = 600
SKIPPED_NO_COMMAND = "skipped_no_command"
RAN = "ran"
REFUSED_FORBID_HOSTS = "forbid_hosts"


def _first_function_id(suite: SuiteDoc) -> str | None:
    return suite.function_ids[0] if suite.function_ids else None


def command_forbid_hits(command: str, config: OverlayConfig) -> list[str]:
    return forbid_host_url_hits(command, config.forbid_hosts)


def run_command(
    command: str,
    *,
    workdir: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", "-c", command],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def run_events_for_suite(
    suite: SuiteDoc,
    *,
    command: str | None,
    exit_code: int | None,
    rule: str | None,
) -> dict[str, object]:
    event: dict[str, object] = {"suite": suite.suite_id, "status": suite.status}
    function_id = _first_function_id(suite)
    if function_id:
        event["function_id"] = function_id
    if rule == SKIPPED_NO_COMMAND:
        event["type"] = SKIPPED_NO_COMMAND
        return event
    if rule == REFUSED_FORBID_HOSTS:
        event["type"] = "refused"
        event["rule"] = REFUSED_FORBID_HOSTS
        event["command"] = command
        return event
    event["type"] = RAN
    event["command"] = command
    event["exit_code"] = exit_code
    return event


def run_run(
    root: Path,
    branch: str,
    write_receipt_dir: Path | None = None,
    workdir: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    workdir = (workdir or Path.cwd()).resolve()
    if not workdir.is_dir():
        print(f"overlay run: workdir is not a directory: {workdir}", file=err)
        return EXIT_CONTRACT

    issues, config, _inboxes, suites = validate_root(root)
    if issues or config is None:
        for issue in issues:
            print(issue, file=err)
        print("overlay run: validate failed", file=err)
        return EXIT_CONTRACT

    selection = select_suites(suites, config, branch)
    assert_errors = assert_selection(selection)
    if assert_errors:
        for message in assert_errors:
            print(message, file=err)
        return EXIT_SELECT_ASSERT

    events = selection_events(selection)
    failed = 0
    skipped = 0
    ran = 0
    refused = 0

    for suite in selection.selected:
        command = suite.product_command
        if not command:
            skipped += 1
            events.append(run_events_for_suite(suite, command=None, exit_code=None, rule=SKIPPED_NO_COMMAND))
            print(f"overlay run: skipped {suite.suite_id} rule={SKIPPED_NO_COMMAND}", file=err)
            print(f"{suite.suite_id} {SKIPPED_NO_COMMAND}", file=out)
            continue

        hits = command_forbid_hits(command, config)
        if hits:
            refused += 1
            events.append(
                run_events_for_suite(suite, command=command, exit_code=None, rule=REFUSED_FORBID_HOSTS)
            )
            print(
                f"overlay run: refused {suite.suite_id} rule={REFUSED_FORBID_HOSTS} hosts={hits}",
                file=err,
            )
            print(f"{suite.suite_id} {REFUSED_FORBID_HOSTS}", file=out)
            continue

        try:
            result = run_command(command, workdir=workdir, timeout=timeout)
            code = result.returncode
            if result.stdout:
                print(result.stdout, file=out, end="" if result.stdout.endswith("\n") else "\n")
            if result.stderr:
                print(result.stderr, file=err, end="" if result.stderr.endswith("\n") else "\n")
        except subprocess.TimeoutExpired:
            code = 124
            print(f"overlay run: {suite.suite_id} timed out after {timeout}s", file=err)
        events.append(run_events_for_suite(suite, command=command, exit_code=code, rule=None))
        ran += 1
        print(f"overlay run: {suite.suite_id} exit={code}", file=err)
        print(f"{suite.suite_id} {code}", file=out)
        if code != 0:
            failed += 1

    if write_receipt_dir is not None:
        sha = git_sha(root)
        receipt = build_receipt(
            wrote_by="run",
            git_sha=sha,
            branch=branch,
            events=events,
            evidence=selection_evidence(suites),
        )
        run_id = os.environ.get("GITHUB_RUN_ID", "").strip() or None
        suffix = f"{run_id}-run" if run_id else None
        filename = receipt_filename(branch, sha, suffix) if suffix else receipt_filename(f"{branch}-run", sha)
        path = write_receipt(write_receipt_dir, receipt, filename)
        print(f"overlay run: wrote {path.as_posix()}", file=err)
    else:
        print("overlay run: no receipt (missing --write-receipt)", file=err)
        return EXIT_CONTRACT

    print(
        f"overlay run: selected={len(selection.selected)} ran={ran} "
        f"skipped={skipped} refused={refused} failed={failed}",
        file=err,
    )
    if refused:
        return EXIT_CONTRACT
    if failed:
        return EXIT_RUN
    return EXIT_OK
