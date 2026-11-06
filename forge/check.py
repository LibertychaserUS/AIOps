"""Local pre-submit gate. No GitHub write. No model. Exit 0 pass / 2 fail.

Locks 代推 (push + open PR), not GitHub merge. Merge stays on required checks.

Thin runner over the closed registry in forge/checks/ (ADR 0009): one
CheckContext per run (config loaded once, base resolved once, diff listed
once), then every check in CHECKS order. The runner owns three disciplines so
no check can forget them: no forge.yaml -> skip, git missing -> that row
fails (exit 2, never a traceback), no visible base -> fail closed.
"""

from __future__ import annotations

import io
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from forge import EXIT_OK
from forge.checks import CHECKS, HIDDEN, NEED_BASE, NEED_FORGE_YAML, NEED_GIT, Check, CheckContext
from forge.checks.base import EXIT_CHECK as EXIT_CHECK
from forge.checks.base import OverlayFn as OverlayFn
from forge.checks.base import SchemaFn as SchemaFn
from forge.checks.base import Step as Step
from forge.checks.base import UnittestFn as UnittestFn
from forge.checks.base import forge_yaml_exists as forge_yaml_exists
from forge.checks.base import is_product_root as is_product_root
from forge.checks.base import is_workshop_root as is_workshop_root
from forge.checks.base import overlay_package_exists as overlay_package_exists
from forge.checks.base import overlay_yaml_exists as overlay_yaml_exists
from forge.checks.base import schema_check_exists as schema_check_exists
from forge.checks.docs_sync import TAG_MENTION_RE as TAG_MENTION_RE
from forge.checks.suite_guard import is_suite_yaml as is_suite_yaml
from forge.checks.unittest_ import CHECK_ENV as CHECK_ENV
from forge.checks.unittest_ import WORKSHOP_UNITTEST_ARGS as WORKSHOP_UNITTEST_ARGS
from forge.checks.unittest_ import workshop_unittest_args as workshop_unittest_args
from forge.config import ForgeError, load_config
from forge.gitutil import GitUnavailable as GitUnavailable
from forge.gitutil import _git as _git
from forge.gitutil import _git_paths as _git_paths
from forge.gitutil import current_branch as current_branch
from forge.gitutil import is_git_work_tree as is_git_work_tree
from forge.gitutil import list_changed_paths as list_changed_paths
from forge.gitutil import matching_agent_prefix as matching_agent_prefix
from forge.gitutil import merge_base_or_ref, resolve_branch, resolve_protect_ref
from forge.gitutil import no_base_detail as no_base_detail
from forge.gitutil import normalize_repo_path as normalize_repo_path
from forge.gitutil import resolve_base_commit as resolve_base_commit
from forge.pathmatch import path_is_denied as path_is_denied
from forge.pathmatch import path_matches_glob as path_matches_glob
from forge.pathmatch import path_matches_pattern as path_matches_pattern
from forge.title import SpecRef, resolve_spec_body, resolve_spec_title

_OMITTED = SpecRef(None, "omitted")


def build_context(
    root: Path,
    env: Mapping[str, str],
    *,
    title_ref: SpecRef = _OMITTED,
    body_ref: SpecRef = _OMITTED,
    head_branch: str | None = None,
    run_unittests: bool = True,
    out: TextIO | None = None,
    err: TextIO | None = None,
    overlay_validate: OverlayFn | None = None,
    overlay_cover: OverlayFn | None = None,
    schema_runner: SchemaFn | None = None,
    unittest_runner: UnittestFn | None = None,
) -> CheckContext:
    """Load forge.yaml once, resolve branch / base / diff once. Never raises for git."""
    config = None
    config_error: str | None = None
    forge_yaml = root / "forge.yaml"
    if forge_yaml.is_file():
        try:
            config = load_config(forge_yaml)
        except ForgeError as exc:
            config_error = exc.message
    branch: str | None = None
    base_ref: str | None = None
    base_commit: str | None = None
    changed: tuple[str, ...] | None = None
    git_error: str | None = None
    if config is not None:
        try:
            if is_git_work_tree(root):
                branch = resolve_branch(root, env, head_branch)
                base_ref = resolve_protect_ref(root, config.protect, env)
                if base_ref:
                    base_commit = merge_base_or_ref(root, base_ref)
                listed = list_changed_paths(root, base_ref)
                changed = tuple(listed) if listed is not None else None
        except GitUnavailable as exc:
            git_error = str(exc)
            branch = base_ref = base_commit = None
            changed = None
    return CheckContext(
        root=root,
        config=config,
        config_error=config_error,
        env=env,
        branch=branch,
        base_ref=base_ref,
        base_commit=base_commit,
        changed=changed,
        title_ref=title_ref,
        body_ref=body_ref,
        head_branch=head_branch,
        run_unittests=run_unittests,
        git_error=git_error,
        out=sys.stdout if out is None else out,
        err=sys.stderr if err is None else err,
        overlay_validate=overlay_validate,
        overlay_cover=overlay_cover,
        schema_runner=schema_runner,
        unittest_runner=unittest_runner,
    )


def run_one(check: Check, ctx: CheckContext) -> Step | None:
    """Run one registered check under the runner disciplines. None = no row."""
    reason = check.applies(ctx)
    if reason == HIDDEN:
        return None
    if reason is not None:
        return Step(check.name, "skip", reason)
    needs = check.needs
    if NEED_FORGE_YAML in needs:
        if ctx.config is None and ctx.config_error is None:
            return Step(check.name, "skip", "no forge.yaml")
        if ctx.config_error is not None:
            return Step(check.name, "fail", ctx.config_error)
    if NEED_GIT in needs and ctx.git_error is not None:
        return Step(check.name, "fail", ctx.git_error)
    try:
        step = check.run(ctx)
    except GitUnavailable as exc:
        return Step(check.name, "fail", str(exc))
    if NEED_BASE in needs and ctx.base_ref is None and step.status == "ok":
        protect = ctx.config.protect if ctx.config is not None else ()
        return Step(check.name, "fail", no_base_detail(protect))
    return step


def _registered(name: str) -> Check:
    for check in CHECKS:
        if check.name == name:
            return check
    raise KeyError(name)


def _standalone(
    name: str,
    root: Path,
    environ: Mapping[str, str] | None,
    head_branch: str | None,
) -> Step:
    env: Mapping[str, str] = os.environ if environ is None else environ
    ctx = build_context(root, env, head_branch=head_branch, out=io.StringIO(), err=io.StringIO())
    step = run_one(_registered(name), ctx)
    assert step is not None
    return step


def deny_paths_step(
    root: Path,
    environ: Mapping[str, str] | None = None,
    *,
    head_branch: str | None = None,
) -> Step:
    """Fail when the local diff touches forge.yaml deny_paths. No GitHub write."""
    return _standalone("deny_paths", root, environ, head_branch)


def suite_guard_step(
    root: Path,
    environ: Mapping[str, str] | None = None,
    *,
    head_branch: str | None = None,
) -> Step:
    """Agent branches must not set or clear blocked. Humans are recorded."""
    return _standalone("suite_guard", root, environ, head_branch)


def docs_sync_step(root: Path, environ: Mapping[str, str] | None = None) -> Step:
    return _standalone("docs_sync", root, environ, None)


def _print_checklist(steps: Sequence[Step], stdout: TextIO) -> None:
    print("forge check", file=stdout)
    width = max(len(step.name) for step in steps)
    for step in steps:
        mark = {"ok": "ok", "fail": "FAIL", "skip": "skip"}[step.status]
        line = f"  {step.name.ljust(width)}  {mark}"
        if step.detail:
            line = f"{line}  {step.detail}"
        print(line, file=stdout)


def run_check(
    root: Path,
    *,
    title: str | None = None,
    body: str | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
    run_unittests: bool = True,
    overlay_validate: OverlayFn | None = None,
    overlay_cover: OverlayFn | None = None,
    schema_runner: SchemaFn | None = None,
    unittest_runner: UnittestFn | None = None,
    head_branch: str | None = None,
) -> int:
    """Run the local pre-submit checklist. Exit 0 / 2. Never writes GitHub.

    Title/body source is event-aware (``resolve_spec_title`` /
    ``resolve_spec_body``). Local omit skips. pull_request + blank fails.
    push lints the HEAD commit subject; it does not skip the title lock.
    ``head_branch`` (submit's resolved --head) beats the checkout's branch.
    """
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    env: Mapping[str, str] = os.environ if environ is None else environ
    root = root.resolve()
    if not is_product_root(root):
        print(
            "forge check: not a product root (no forge.yaml or overlay.yaml); "
            "cd to the product first",
            file=err,
        )
        return EXIT_CHECK
    ctx = build_context(
        root,
        env,
        title_ref=resolve_spec_title(title, env, root),
        body_ref=resolve_spec_body(body, env),
        head_branch=head_branch,
        run_unittests=run_unittests,
        out=out,
        err=err,
        overlay_validate=overlay_validate,
        overlay_cover=overlay_cover,
        schema_runner=schema_runner,
        unittest_runner=unittest_runner,
    )
    steps: list[Step] = []
    for check in CHECKS:
        step = run_one(check, ctx)
        if step is not None:
            steps.append(step)

    _print_checklist(steps, out)
    failed = [step for step in steps if step.status == "fail"]
    if failed:
        print(f"forge check: red ({len(failed)} failed)", file=err)
        return EXIT_CHECK
    print("forge check: ok", file=out)
    return EXIT_OK
