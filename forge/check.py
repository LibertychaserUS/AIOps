"""Local pre-submit gate. No GitHub write. No model. Exit 0 pass / 2 fail.

Locks 代推 (push + open PR), not GitHub merge. Merge stays on required checks.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from forge import EXIT_OK
from forge.apply import ForgeError, load_config
from forge.brief import brief_spec_exists, lint_pr_body
from forge.title import run_pr_title

EXIT_CHECK = 2
CHECK_ENV = "FORGE_CHECK_RUNNING"

# Title grammar only. Never include test_submit / test_check (they call check).
FAST_UNITTEST_MODULES = ("tests.forge.test_title",)
FAST_UNITTEST_FILES = (Path("tests") / "forge" / "test_title.py",)

OverlayFn = Callable[[Path, TextIO, TextIO], int]
SchemaFn = Callable[[Path, TextIO, TextIO], int]
UnittestFn = Callable[[Path, Sequence[str], TextIO, TextIO], int]


@dataclass(frozen=True)
class Step:
    name: str
    status: str  # ok | fail | skip
    detail: str = ""


def overlay_yaml_exists(root: Path) -> bool:
    return (root / "overlay.yaml").is_file()


def schema_check_exists(root: Path) -> bool:
    return (root / "schema" / "check.py").is_file()


def workshop_fast_test_modules(root: Path) -> list[str]:
    modules: list[str] = []
    for rel, module in zip(FAST_UNITTEST_FILES, FAST_UNITTEST_MODULES):
        if (root / rel).is_file():
            modules.append(module)
    return modules


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def is_git_work_tree(root: Path) -> bool:
    proc = _git(root, "rev-parse", "--is-inside-work-tree")
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def current_branch(root: Path) -> str | None:
    proc = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if proc.returncode != 0:
        return None
    name = proc.stdout.strip()
    if not name or name == "HEAD":
        return None
    return name


def resolve_protect_ref(root: Path, protect: Sequence[str]) -> str | None:
    for name in protect:
        for candidate in (
            f"refs/heads/{name}",
            name,
            f"origin/{name}",
            f"refs/remotes/origin/{name}",
        ):
            proc = _git(root, "rev-parse", "--verify", "--quiet", candidate)
            if proc.returncode == 0:
                return candidate
    return None


def normalize_repo_path(path: str) -> str:
    rel = path.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def path_is_denied(path: str, deny_paths: Sequence[str]) -> bool:
    rel = normalize_repo_path(path)
    for deny in deny_paths:
        target = normalize_repo_path(str(deny))
        if not target:
            continue
        if rel == target:
            return True
        if target.endswith("/") and rel.startswith(target):
            return True
        if not target.endswith("/") and rel.startswith(target + "/"):
            return True
    return False


def list_changed_paths(root: Path, base_ref: str | None) -> list[str] | None:
    """Changed paths vs protect merge-base (or HEAD). None if not a git work tree."""
    if not is_git_work_tree(root):
        return None
    paths: set[str] = set()
    if base_ref:
        merge = _git(root, "merge-base", "HEAD", base_ref)
        base = merge.stdout.strip() if merge.returncode == 0 and merge.stdout.strip() else base_ref
        for args in (
            ("diff", "--name-only", "--no-renames", base),
            ("diff", "--name-only", "--no-renames", "--cached", base),
        ):
            proc = _git(root, *args)
            if proc.returncode == 0:
                paths.update(normalize_repo_path(line) for line in proc.stdout.splitlines() if line.strip())
    else:
        for args in (
            ("diff", "--name-only", "--no-renames", "HEAD"),
            ("diff", "--name-only", "--no-renames", "--cached"),
        ):
            proc = _git(root, *args)
            if proc.returncode == 0:
                paths.update(normalize_repo_path(line) for line in proc.stdout.splitlines() if line.strip())
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    if untracked.returncode == 0:
        paths.update(normalize_repo_path(line) for line in untracked.stdout.splitlines() if line.strip())
    return sorted(p for p in paths if p)


def matching_agent_prefix(branch: str | None, prefixes: Sequence[str]) -> str | None:
    if not branch:
        return None
    for prefix in prefixes:
        if branch.startswith(prefix):
            return prefix
    return None


def deny_paths_step(root: Path) -> Step:
    """Fail when the local diff touches forge.yaml deny_paths. No GitHub write.

    agent_branch_prefixes are recorded (design 3.5.2: human branches stay allowed).
    They are not a local fail in this cut.
    """
    forge_yaml = root / "forge.yaml"
    if not forge_yaml.is_file():
        return Step("deny_paths", "skip", "no forge.yaml")
    try:
        config = load_config(forge_yaml)
    except ForgeError as exc:
        return Step("deny_paths", "fail", exc.message)
    if not is_git_work_tree(root):
        return Step("deny_paths", "skip", "no git work tree")
    base = resolve_protect_ref(root, config.protect)
    changed = list_changed_paths(root, base)
    if changed is None:
        return Step("deny_paths", "skip", "no git work tree")
    hits = [path for path in changed if path_is_denied(path, config.deny_paths)]
    branch = current_branch(root)
    prefix = matching_agent_prefix(branch, config.agent_branch_prefixes)
    suffix = f"; agent branch {branch}" if prefix and branch else ""
    if hits:
        shown = ", ".join(hits)
        return Step("deny_paths", "fail", f"diff touches {shown}{suffix}")
    if base:
        return Step("deny_paths", "ok", f"vs {base}{suffix}")
    return Step("deny_paths", "ok", f"no protect ref{suffix}")


def _print_captured(text: str, stream: TextIO) -> None:
    if not text:
        return
    if text.endswith("\n"):
        print(text, file=stream, end="")
    else:
        print(text, file=stream)


def _default_overlay_validate(root: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        from overlay.validate import run_validate
    except ImportError as exc:
        print(f"overlay validate: cannot import overlay ({exc})", file=stderr)
        return EXIT_CHECK
    return run_validate(root, stdout=stdout, stderr=stderr)


def _default_overlay_cover(root: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        from overlay.cover import run_cover
    except ImportError as exc:
        print(f"overlay cover: cannot import overlay ({exc})", file=stderr)
        return EXIT_CHECK
    return run_cover(root, stdout=stdout, stderr=stderr)


def _default_schema_runner(root: Path, stdout: TextIO, stderr: TextIO) -> int:
    script = root / "schema" / "check.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    _print_captured(proc.stdout, stdout)
    if proc.returncode != 0:
        _print_captured(proc.stderr or "schema/check.py failed", stderr)
        return EXIT_CHECK
    return EXIT_OK


def _default_unittest_runner(
    root: Path,
    modules: Sequence[str],
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    env = os.environ.copy()
    env[CHECK_ENV] = "1"
    pythonpath = str(root)
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath = pythonpath + os.pathsep + existing
    env["PYTHONPATH"] = pythonpath
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", *modules, "-q"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    _print_captured(proc.stdout, stdout)
    if proc.returncode != 0:
        _print_captured(proc.stderr or "unittest failed", stderr)
        return EXIT_CHECK
    return EXIT_OK


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
) -> int:
    """Run the local pre-submit checklist. Exit 0 / 2. Never writes GitHub.

    Title/body steps skip when omitted. That is not the same object as CI
    `pr-title`, which reads the GitHub PR title and body.
    """
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    env: Mapping[str, str] = os.environ if environ is None else environ
    root = root.resolve()
    steps: list[Step] = []
    resolved_title = title if title is not None else env.get("PR_TITLE")
    resolved_body = body if body is not None else env.get("PR_BODY")

    if overlay_yaml_exists(root):
        validate_fn = _default_overlay_validate if overlay_validate is None else overlay_validate
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        code = validate_fn(root, buf_out, buf_err)
        _print_captured(buf_err.getvalue(), err)
        if code != EXIT_OK:
            steps.append(Step("overlay validate", "fail", f"exit {code}"))
        else:
            steps.append(Step("overlay validate", "ok", _last_line(buf_out.getvalue())))

        cover_fn = _default_overlay_cover if overlay_cover is None else overlay_cover
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        code = cover_fn(root, buf_out, buf_err)
        _print_captured(buf_err.getvalue(), err)
        if code != EXIT_OK:
            steps.append(Step("overlay cover", "fail", f"exit {code}"))
        else:
            steps.append(Step("overlay cover", "ok", _last_line(buf_out.getvalue())))
    else:
        steps.append(Step("overlay validate", "skip", "no overlay.yaml"))
        steps.append(Step("overlay cover", "skip", "no overlay.yaml"))

    if resolved_title is not None:
        buf_err = io.StringIO()
        code = run_pr_title(title=resolved_title, environ=env, stdout=out, stderr=buf_err)
        _print_captured(buf_err.getvalue(), err)
        if code != EXIT_OK:
            steps.append(Step("pr-title", "fail", buf_err.getvalue().strip() or f"exit {code}"))
        else:
            steps.append(Step("pr-title", "ok", resolved_title))
    else:
        steps.append(Step("pr-title", "skip", "no --title; CI lints PR_TITLE"))

    if brief_spec_exists(root):
        if resolved_body is not None:
            code, message = lint_pr_body(resolved_body)
            if code != EXIT_OK:
                steps.append(Step("pr-body", "fail", message or f"exit {code}"))
            else:
                steps.append(Step("pr-body", "ok", "six ## headings"))
        else:
            steps.append(Step("pr-body", "skip", "no --body; CI lints PR_BODY"))
    else:
        steps.append(Step("pr-body", "skip", "no docs/pr-brief.md"))

    if schema_check_exists(root):
        schema_fn = _default_schema_runner if schema_runner is None else schema_runner
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        code = schema_fn(root, buf_out, buf_err)
        _print_captured(buf_err.getvalue(), err)
        if code != EXIT_OK:
            steps.append(Step("schema/check.py", "fail", f"exit {code}"))
        else:
            steps.append(Step("schema/check.py", "ok", _last_line(buf_out.getvalue())))
    else:
        steps.append(Step("schema/check.py", "skip", "no schema/ (adopter product root)"))

    from forge.sop_lock import run_sop_lock

    buf_out = io.StringIO()
    buf_err = io.StringIO()
    code = run_sop_lock(root, stdout=buf_out, stderr=buf_err)
    _print_captured(buf_err.getvalue(), err)
    if code != EXIT_OK:
        steps.append(Step("sop-lock", "fail", _last_line(buf_err.getvalue()) or f"exit {code}"))
    else:
        steps.append(Step("sop-lock", "ok", _last_line(buf_out.getvalue())))

    steps.append(deny_paths_step(root))

    nested = bool(env.get(CHECK_ENV)) or bool(os.environ.get(CHECK_ENV))
    modules = workshop_fast_test_modules(root)
    if not run_unittests:
        steps.append(Step("unittest (fast)", "skip", "disabled"))
    elif nested:
        steps.append(Step("unittest (fast)", "skip", "already inside forge check"))
    elif not modules:
        steps.append(Step("unittest (fast)", "skip", "no workshop tests/"))
    else:
        unit_fn = _default_unittest_runner if unittest_runner is None else unittest_runner
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        code = unit_fn(root, modules, buf_out, buf_err)
        _print_captured(buf_err.getvalue(), err)
        if code != EXIT_OK:
            steps.append(Step("unittest (fast)", "fail", f"exit {code}"))
        else:
            steps.append(Step("unittest (fast)", "ok", " ".join(modules)))

    _print_checklist(steps, out)
    failed = [step for step in steps if step.status == "fail"]
    if failed:
        print(f"forge check: red ({len(failed)} failed)", file=err)
        return EXIT_CHECK
    print("forge check: ok", file=out)
    return EXIT_OK
