"""Local pre-submit gate. No GitHub write. No model. Exit 0 pass / 2 fail.

Locks 代推 (push + open PR), not GitHub merge. Merge stays on required checks.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from forge import EXIT_OK
from forge.apply import ForgeError, load_config
from forge.brief import brief_spec_exists, lint_pr_body
from forge.status import state_is_fresh
from forge.title import resolve_spec_body, resolve_spec_title, run_pr_title

EXIT_CHECK = 2
CHECK_ENV = "FORGE_CHECK_RUNNING"

# Same command as the CI job `unittest`. Adopter roots never reach this.
WORKSHOP_UNITTEST_ARGS = ("discover", "-s", "tests", "-t", ".", "-q")

OverlayFn = Callable[[Path, TextIO, TextIO], int]
SchemaFn = Callable[[Path, TextIO, TextIO], int]
UnittestFn = Callable[[Path, Sequence[str], TextIO, TextIO], int]


@dataclass(frozen=True)
class Step:
    name: str
    status: str  # ok | fail | skip
    detail: str = ""


def overlay_package_exists(root: Path) -> bool:
    return (root / "overlay" / "__init__.py").is_file()


def is_workshop_root(root: Path) -> bool:
    return overlay_package_exists(root)


def overlay_yaml_exists(root: Path) -> bool:
    return (root / "overlay.yaml").is_file()


def forge_yaml_exists(root: Path) -> bool:
    return (root / "forge.yaml").is_file()


def is_product_root(root: Path) -> bool:
    return overlay_yaml_exists(root) or forge_yaml_exists(root)


def schema_check_exists(root: Path) -> bool:
    return (root / "schema" / "check.py").is_file()


def workshop_unittest_args(root: Path) -> tuple[str, ...] | None:
    """Full discover, matching CI. None when this root has no workshop tests/."""
    if not (root / "tests").is_dir():
        return None
    return WORKSHOP_UNITTEST_ARGS


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


class GitUnavailable(Exception):
    """git is not on PATH: a diff gate cannot see anything, so it fails."""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # quotePath=false: a quoted "secret/\345..." would never match deny_paths.
    try:
        return subprocess.run(
            ["git", "-C", str(root), "-c", "core.quotePath=false", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GitUnavailable(f"cannot run git ({exc})") from exc


def _git_paths(root: Path, *args: str) -> list[str] | None:
    """NUL-separated path listing (-z): no quoting, no newline ambiguity."""
    proc = _git(root, args[0], "-z", *args[1:])
    if proc.returncode != 0:
        return None
    return [normalize_repo_path(item) for item in proc.stdout.split("\0") if item.strip()]


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


def resolve_protect_ref(
    root: Path,
    protect: Sequence[str],
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """The PR base is the remote protect branch; a stale local copy must not win.

    Last resort is the Actions PR base (origin/$GITHUB_BASE_REF). None means the
    diff gates cannot see the base; callers fail closed instead of diffing HEAD.
    """
    for name in protect:
        for candidate in (
            f"refs/remotes/origin/{name}",
            f"origin/{name}",
            f"refs/heads/{name}",
            name,
        ):
            proc = _git(root, "rev-parse", "--verify", "--quiet", candidate)
            if proc.returncode == 0:
                return candidate
    env = os.environ if environ is None else environ
    base = (env.get("GITHUB_BASE_REF") or "").strip()
    if base:
        candidate = f"refs/remotes/origin/{base}"
        if _git(root, "rev-parse", "--verify", "--quiet", candidate).returncode == 0:
            return candidate
    return None


def no_base_detail(protect: Sequence[str]) -> str:
    name = protect[0] if protect else "main"
    return (
        f"cannot see the base: no origin/{name} (or local {name}); "
        f"run git fetch origin {name} and re-run"
    )


def normalize_repo_path(path: str) -> str:
    rel = path.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


_GLOB_CHARS = frozenset("*?[")


def _glob_regex(pattern: str) -> str:
    """gitignore-style: `**/` = zero or more dirs, `*` / `?` stay inside one segment."""
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if pattern.startswith("**", i):
            at_start = i == 0 or pattern[i - 1] == "/"
            j = i + 2
            if at_start and j < n and pattern[j] == "/":
                out.append("(?:.*/)?")
                i = j + 1
                continue
            if at_start and j == n:
                # "dir/**" also names dir itself (prior behavior); "**" is everything.
                if out and out[-1] == "/":
                    out[-1] = "(?:/.*)?"
                else:
                    out.append(".*")
                i = j
                continue
            out.append("[^/]*")
            i = j
            continue
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        elif ch == "[":
            end = pattern.find("]", i + 2 if pattern[i + 1 : i + 2] in ("!", "^") else i + 1)
            if end == -1:
                out.append(re.escape(ch))
            else:
                body = pattern[i + 1 : end]
                if body[:1] in ("!", "^"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\").replace("[", "\\[") + "]")
                i = end + 1
                continue
        elif ch == "/":
            out.append("/")
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


def path_matches_pattern(path: str, pattern: str) -> bool:
    """One matcher for deny_paths and docs_sync.paths (see docs/forge-config.md).

    Plain path: exact file or directory prefix. Trailing `/`: directory prefix.
    Globs: `**/` matches zero or more directories, `*` and `?` never cross `/`;
    a glob with no `/` matches a basename at any depth. A glob that names a
    directory also covers everything under it.
    """
    rel = normalize_repo_path(path)
    pat = normalize_repo_path(str(pattern)).lstrip("/")
    if pat.endswith("/"):
        pat = pat.rstrip("/")
    if not pat or not rel:
        return False
    if not _GLOB_CHARS.intersection(pat):
        return rel == pat or rel.startswith(pat + "/")
    regex = _glob_regex(pat)
    if "/" not in pat:
        regex = "(?:.*/)?" + regex
    return re.fullmatch(regex + "(?:/.*)?", rel) is not None


def path_is_denied(path: str, deny_paths: Sequence[str]) -> bool:
    return any(path_matches_pattern(path, deny) for deny in deny_paths)


def list_changed_paths(root: Path, base_ref: str | None) -> list[str] | None:
    """Changed paths under root vs protect merge-base (or HEAD), relative to root.

    Union of committed (base..HEAD), index and worktree: a staged revert must
    not hide a committed change that the push still carries.
    --relative keeps a monorepo product's deny_paths meaningful when --root is a
    subdirectory; untracked files from ls-files are already cwd-relative.
    None if not a git work tree.
    """
    if not is_git_work_tree(root):
        return None
    paths: set[str] = set()
    diff = ("diff", "--name-only", "--no-renames", "--relative")
    if base_ref:
        merge = _git(root, "merge-base", "HEAD", base_ref)
        base = merge.stdout.strip() if merge.returncode == 0 and merge.stdout.strip() else base_ref
        listings = ((*diff, base, "HEAD"), (*diff, base), (*diff, "--cached", base))
    else:
        listings = ((*diff, "HEAD"), (*diff, "--cached"))
    for args in (*listings, ("ls-files", "--others", "--exclude-standard")):
        found = _git_paths(root, *args)
        if found is not None:
            paths.update(found)
    return sorted(p for p in paths if p)


def matching_agent_prefix(branch: str | None, prefixes: Sequence[str]) -> str | None:
    if not branch:
        return None
    for prefix in prefixes:
        if branch.startswith(prefix):
            return prefix
    return None


def deny_paths_step(
    root: Path,
    environ: Mapping[str, str] | None = None,
    *,
    head_branch: str | None = None,
) -> Step:
    """Fail when the local diff touches forge.yaml deny_paths. No GitHub write.

    agent_branch_prefixes are recorded (design 3.5.2: human branches stay allowed).
    They are not a local fail in this cut. No visible base fails closed.
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
    base = resolve_protect_ref(root, config.protect, environ)
    changed = list_changed_paths(root, base)
    if changed is None:
        return Step("deny_paths", "skip", "no git work tree")
    hits = [path for path in changed if path_is_denied(path, config.deny_paths)]
    branch = resolve_branch(root, environ, head_branch)
    prefix = matching_agent_prefix(branch, config.agent_branch_prefixes)
    suffix = f"; agent branch {branch}" if prefix and branch else ""
    if hits:
        shown = ", ".join(hits)
        return Step("deny_paths", "fail", f"diff touches {shown}{suffix}")
    if not base:
        return Step("deny_paths", "fail", no_base_detail(config.protect))
    return Step("deny_paths", "ok", f"vs {base}{suffix}")


def resolve_branch(
    root: Path,
    environ: Mapping[str, str] | None = None,
    head_branch: str | None = None,
) -> str | None:
    """Explicit head (submit --head), branch name locally, or the CI PR head.

    None when nothing names the branch; suite_guard then treats it as an agent.
    """
    if head_branch and head_branch.strip():
        return head_branch.strip()
    name = current_branch(root)
    if name:
        return name
    env = os.environ if environ is None else environ
    for key in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
        value = (env.get(key) or "").strip()
        if value:
            return value
    return None


def resolve_base_commit(
    root: Path,
    protect: Sequence[str],
    environ: Mapping[str, str] | None = None,
) -> str | None:
    base_ref = resolve_protect_ref(root, protect, environ)
    if not base_ref:
        return None
    merge = _git(root, "merge-base", "HEAD", base_ref)
    if merge.returncode == 0 and merge.stdout.strip():
        return merge.stdout.strip()
    return base_ref


def is_suite_yaml(path: str) -> bool:
    rel = normalize_repo_path(path)
    return rel.startswith("suites/") and rel.endswith("/suite.yaml")


def _suite_status(text: str | None) -> str:
    """status from suite.yaml text; blank when absent."""
    if not text:
        return ""
    try:
        import yaml
    except ImportError:
        return ""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("status") or "").strip()


def _show_at(root: Path, base: str, rel: str) -> str | None:
    # ./ makes the path relative to --root even when root is a repo subdirectory.
    proc = _git(root, "show", f"{base}:./{rel}")
    return proc.stdout if proc.returncode == 0 else None


def suite_guard_step(
    root: Path,
    environ: Mapping[str, str] | None = None,
    *,
    head_branch: str | None = None,
) -> Step:
    """Agent branches must not set or clear blocked. Humans are recorded.

    An unnamed branch (detached HEAD, no CI env) is an agent: fail closed.
    """
    forge_yaml = root / "forge.yaml"
    if not forge_yaml.is_file():
        return Step("suite_guard", "skip", "no forge.yaml")
    try:
        config = load_config(forge_yaml)
    except ForgeError as exc:
        return Step("suite_guard", "fail", exc.message)
    if not is_git_work_tree(root):
        return Step("suite_guard", "skip", "no git work tree")
    resolved = resolve_branch(root, environ, head_branch)
    prefix = matching_agent_prefix(resolved, config.agent_branch_prefixes)
    if resolved and not prefix:
        return Step("suite_guard", "ok", f"human branch {resolved}; status changes are reviewed, not blocked")
    branch = resolved or "(detached HEAD, unnamed)"
    base_ref = resolve_protect_ref(root, config.protect, environ)
    if not base_ref:
        return Step("suite_guard", "fail", f"agent branch {branch}: {no_base_detail(config.protect)}")
    base = resolve_base_commit(root, config.protect, environ)
    changed = list_changed_paths(root, base_ref) or []
    suites = [path for path in changed if is_suite_yaml(path)]
    if not suites:
        return Step("suite_guard", "ok", f"no suite.yaml changed; agent branch {branch}")
    hits: list[str] = []
    for rel in suites:
        new_path = root / rel
        new_text = new_path.read_text(encoding="utf-8") if new_path.is_file() else None
        old_text = _show_at(root, base, rel) if base else None
        new_present = new_text is not None
        old_present = old_text is not None
        new_status = _suite_status(new_text) or ("active" if new_present else "")
        old_status = _suite_status(old_text) or ("active" if old_present else "")
        if new_status == "blocked" and old_status != "blocked":
            hits.append(f"{rel} (status {old_status or 'none'} -> blocked)")
        elif old_status == "blocked" and new_status != "blocked":
            shown = new_status or "deleted"
            hits.append(f"{rel} (status blocked -> {shown})")
    if hits:
        return Step(
            "suite_guard",
            "fail",
            "agent branch "
            f"{branch} must not set or clear blocked: {', '.join(hits)}; a human writes that status",
        )
    return Step("suite_guard", "ok", f"suite.yaml edits do not introduce blocked; agent branch {branch}")


def path_matches_glob(path: str, pattern: str) -> bool:
    return path_matches_pattern(path, pattern)


def _git_tags(root: Path) -> set[str]:
    proc = _git(root, "tag", "-l")
    if proc.returncode != 0:
        return set()
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def _changelog_headings(root: Path) -> set[str]:
    path = root / "CHANGELOG.md"
    if not path.is_file():
        return set()
    headings: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## ["):
            inner = stripped[4:]
            if "]" in inner:
                headings.add(inner.split("]", 1)[0])
    return headings


def _markdown_files(root: Path) -> list[Path]:
    """Tracked + unignored *.md under root (git ls-files); falls back to rglob outside git."""
    if is_git_work_tree(root):
        listed = _git_paths(root, "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.md", "**/*.md")
        if listed is not None:
            seen: set[str] = set()
            out: list[Path] = []
            for rel in listed:
                if rel and rel not in seen and (root / rel).is_file():
                    seen.add(rel)
                    out.append(root / rel)
            return sorted(out)
    return sorted(p for p in root.rglob("*.md") if ".git" not in p.parts)


def _relative_link_failures(root: Path) -> list[str]:
    import re

    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    failures: list[str] = []
    for path in _markdown_files(root):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in link_re.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#", "<", "/")):
                # "/x" is a site-root web path (served from public/), not a repo path.
                continue
            path_part = target.split("#", 1)[0].split("?", 1)[0]
            if not path_part:
                continue
            dest = (path.parent / path_part).resolve()
            try:
                dest.relative_to(root.resolve())
            except ValueError:
                failures.append(f"{rel.as_posix()} -> {target}")
                continue
            if not dest.exists():
                failures.append(f"{rel.as_posix()} -> {target}")
    return failures


TAG_MENTION_RE = re.compile(r"(overlay|forge)-v(\d+\.\d+\.\d+)")


def _pin_mention_failures(root: Path) -> list[str]:
    tags = _git_tags(root)
    headings = _changelog_headings(root)
    failures: list[str] = []
    for path in _markdown_files(root):
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in TAG_MENTION_RE.finditer(text):
            tag = match.group(0)
            product, version = match.group(1), match.group(2)
            heading = f"{product}-{version}"
            if tag in tags or heading in headings:
                continue
            failures.append(f"{rel} mentions {tag} (not a git tag and not ## [{heading}] in CHANGELOG.md)")
    return failures


def docs_sync_step(root: Path, environ: Mapping[str, str] | None = None) -> Step:
    forge_yaml = root / "forge.yaml"
    if not forge_yaml.is_file():
        return Step("docs_sync", "skip", "no forge.yaml")
    try:
        config = load_config(forge_yaml)
    except ForgeError as exc:
        return Step("docs_sync", "fail", exc.message)
    misses: list[str] = []
    if is_git_work_tree(root):
        base_ref = resolve_protect_ref(root, config.protect, environ)
        if config.docs_sync and not base_ref:
            misses.append(no_base_detail(config.protect))
        changed = list_changed_paths(root, base_ref) if base_ref else []
        for rule in config.docs_sync:
            if any(path_matches_pattern(path, pattern) for path in changed or [] for pattern in rule.paths):
                if not any(normalize_repo_path(req) in (changed or []) for req in rule.require):
                    misses.append(
                        "changed "
                        + ", ".join(rule.paths)
                        + " but missing "
                        + ", ".join(rule.require)
                    )
    misses.extend(_relative_link_failures(root))
    if is_workshop_root(root):
        # overlay-v*/forge-v* tags live in the tool repo; adopters may cite them freely.
        misses.extend(_pin_mention_failures(root))
    state_path = root / "docs" / "STATE.md"
    if state_path.is_file():
        ok, message = state_is_fresh(root, config, state_path.read_text(encoding="utf-8"))
        if not ok:
            misses.append(message)
    if misses:
        shown = "; ".join(misses[:8])
        extra = f" (+{len(misses) - 8} more)" if len(misses) > 8 else ""
        return Step("docs_sync", "fail", shown + extra)
    return Step("docs_sync", "ok", "table + links + pins")


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
        [sys.executable, "-m", "unittest", *modules],
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


def _git_step(name: str, fn: Callable[[], Step]) -> Step:
    try:
        return fn()
    except GitUnavailable as exc:
        return Step(name, "fail", str(exc))


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
    steps: list[Step] = []
    title_ref = resolve_spec_title(title, env, root)
    body_ref = resolve_spec_body(body, env)
    resolved_title = title_ref.text
    resolved_body = body_ref.text

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
        code = run_pr_title(
            title=resolved_title,
            environ=env,
            stdout=out,
            stderr=buf_err,
            root=root,
        )
        _print_captured(buf_err.getvalue(), err)
        if code != EXIT_OK:
            steps.append(Step("pr-title", "fail", buf_err.getvalue().strip() or f"exit {code}"))
        else:
            steps.append(Step("pr-title", "ok", f"{title_ref.source}: {resolved_title}"))
    else:
        steps.append(Step("pr-title", "skip", "no spec; pull_request lints PR_TITLE, push lints commit"))

    if brief_spec_exists(root):
        if resolved_body is not None:
            code, message = lint_pr_body(resolved_body)
            if code != EXIT_OK:
                steps.append(Step("pr-body", "fail", message or f"exit {code}"))
            else:
                steps.append(Step("pr-body", "ok", "six ## headings"))
        else:
            steps.append(Step("pr-body", "skip", "no spec; pull_request lints PR_BODY"))
    else:
        steps.append(Step("pr-body", "skip", "no docs/pr-brief.md"))

    steps.append(_git_step("deny_paths", lambda: deny_paths_step(root, env, head_branch=head_branch)))
    steps.append(_git_step("suite_guard", lambda: suite_guard_step(root, env, head_branch=head_branch)))
    steps.append(_git_step("docs_sync", lambda: docs_sync_step(root, env)))

    workshop = is_workshop_root(root)
    if workshop:
        from forge.sop_lock import run_sop_lock

        buf_out = io.StringIO()
        buf_err = io.StringIO()
        code = run_sop_lock(root, stdout=buf_out, stderr=buf_err)
        _print_captured(buf_err.getvalue(), err)
        if code != EXIT_OK:
            steps.append(Step("sop-lock", "fail", _last_line(buf_err.getvalue()) or f"exit {code}"))
        else:
            steps.append(Step("sop-lock", "ok", _last_line(buf_out.getvalue())))

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

        nested = bool(env.get(CHECK_ENV)) or bool(os.environ.get(CHECK_ENV))
        modules = workshop_unittest_args(root)
        if not run_unittests:
            steps.append(Step("unittest", "skip", "disabled"))
        elif nested:
            steps.append(Step("unittest", "skip", "already inside forge check"))
        elif not modules:
            steps.append(Step("unittest", "skip", "no workshop tests/"))
        else:
            unit_fn = _default_unittest_runner if unittest_runner is None else unittest_runner
            buf_out = io.StringIO()
            buf_err = io.StringIO()
            code = unit_fn(root, modules, buf_out, buf_err)
            _print_captured(buf_err.getvalue(), err)
            if code != EXIT_OK:
                steps.append(Step("unittest", "fail", f"exit {code}"))
            else:
                steps.append(Step("unittest", "ok", " ".join(modules)))

    _print_checklist(steps, out)
    failed = [step for step in steps if step.status == "fail"]
    if failed:
        print(f"forge check: red ({len(failed)} failed)", file=err)
        return EXIT_CHECK
    print("forge check: ok", file=out)
    return EXIT_OK
