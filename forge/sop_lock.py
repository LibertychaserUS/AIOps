"""Decidable SOP locks. No model. Exit 0 pass / 2 fail.

Locks the machine-checkable subset of skills/*/SKILL.md — not NLP over prose.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

import yaml

from forge import EXIT_OK

EXIT_SOP = 2

WORKSHOP_REQUIRED_CHECKS = ("overlay-check", "pr-title", "sop-lock")
LOCK_HEADING_RE = re.compile(r"^## Lock\b", re.MULTILINE)
GENERATE_RUN_RE = re.compile(
    r"(python[0-9.]*\s+-m\s+overlay\s+generate)|(\boverlay\s+generate\b)",
    re.IGNORECASE,
)
UNITTEST_RE = re.compile(r"unittest\s+discover")
FLOATING_USES_RE = re.compile(
    r"^[^/]+/[^/]+/.+@(main|master|HEAD|latest)$",
    re.IGNORECASE,
)
BANNED_USES_RE = (
    re.compile(r"LearningGuidePortal", re.IGNORECASE),
    re.compile(r"/Verify(\.yml)?(@|$)", re.IGNORECASE),
    re.compile(r"\.github/workflows/ci\.yml", re.IGNORECASE),
)
KERNEL_BANNED = ("ilovelearningguide", "LearningGuidePortal", "LearningGuide")
OPENAI_KEYS = frozenset({"OPENAI_API_KEY", "OPENAI_API_KEY_OVERRIDE"})


@dataclass(frozen=True)
class Issue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def is_workshop_root(root: Path) -> bool:
    return (
        (root / "overlay" / "__init__.py").is_file()
        and (root / "forge" / "__init__.py").is_file()
        and (root / "skills" / "use-overlay" / "SKILL.md").is_file()
        and (root / "docs" / "sop.md").is_file()
    )


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _on_has(on_field: Any, event: str) -> bool:
    if on_field == event:
        return True
    if isinstance(on_field, list) and event in on_field:
        return True
    if isinstance(on_field, dict) and event in on_field:
        return True
    return False


def _walk(node: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key), value
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _collect_runs(node: Any) -> list[str]:
    return [value for key, value in _walk(node) if key == "run" and isinstance(value, str)]


def _collect_uses(node: Any) -> list[str]:
    return [value.strip() for key, value in _walk(node) if key == "uses" and isinstance(value, str)]


def _collect_env_keys(node: Any) -> list[str]:
    keys: list[str] = []
    for key, value in _walk(node):
        if key == "env" and isinstance(value, dict):
            keys.extend(str(item) for item in value.keys())
        if key in OPENAI_KEYS:
            keys.append(key)
    return keys


def _job_ids(data: dict[str, Any]) -> list[str]:
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        return []
    return [str(name) for name in jobs]


def _load_workflow(path: Path) -> dict[str, Any] | None:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return loaded if isinstance(loaded, dict) else None


def check_workflows(root: Path) -> list[Issue]:
    folder = root / ".github" / "workflows"
    if not folder.is_dir():
        return []
    issues: list[Issue] = []
    for path in sorted(folder.glob("*.yml")) + sorted(folder.glob("*.yaml")):
        rel = _rel(root, path)
        data = _load_workflow(path)
        if data is None:
            issues.append(Issue(rel, "workflow is not a YAML mapping"))
            continue
        on_field = data.get("on") or data.get(True)
        push = _on_has(on_field, "push")
        runs = _collect_runs(data)
        uses = _collect_uses(data)
        env_keys = _collect_env_keys(data)
        if push:
            for script in runs:
                if GENERATE_RUN_RE.search(script):
                    issues.append(Issue(rel, "push workflow must not run overlay generate"))
                    break
            for job in _job_ids(data):
                if job.lower() == "generate":
                    issues.append(Issue(rel, "push workflow must not have a generate job"))
            if any(key in OPENAI_KEYS for key in env_keys) or any(
                "OPENAI_API_KEY" in script for script in runs
            ):
                issues.append(Issue(rel, "push workflow must not set OPENAI_API_KEY"))
            if any(UNITTEST_RE.search(script) for script in runs):
                issues.append(
                    Issue(
                        rel,
                        "do not add a unittest workflow that bypasses Overlay select "
                        "(put tests in an armed product_command)",
                    )
                )
        for ref in uses:
            for banned in BANNED_USES_RE:
                if banned.search(ref):
                    issues.append(
                        Issue(rel, f"must not workflow_call product ci.yml / Verify ({ref})")
                    )
                    break
            if FLOATING_USES_RE.match(ref):
                issues.append(Issue(rel, f"reusable workflow uses: must pin tag or SHA, not {ref}"))
        for key, value in _walk(data):
            if key == "repository" and isinstance(value, str) and "LearningGuidePortal" in value:
                issues.append(Issue(rel, "must not checkout LearningGuidePortal"))
                break
    return issues


def check_kernel(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    overlay_dir = root / "overlay"
    if overlay_dir.is_dir():
        for path in sorted(overlay_dir.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for token in KERNEL_BANNED:
                if token in text:
                    issues.append(Issue(_rel(root, path), f"kernel must not contain {token!r}"))
    check_py = root / "schema" / "check.py"
    if check_py.is_file():
        proc = subprocess.run(
            [sys.executable, str(check_py)],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "failed").strip().splitlines()
            message = detail[0] if detail else "schema/check.py failed"
            issues.append(Issue("schema/check.py", message))
    return issues


def check_husky(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    if (root / ".husky").exists():
        issues.append(Issue(".husky/", "do not install husky; merge lock is GitHub checks"))
    package = root / "package.json"
    if package.is_file() and "husky" in package.read_text(encoding="utf-8"):
        issues.append(Issue("package.json", "do not add husky; CPython sop-lock / pr-title only"))
    return issues


def check_skills(root: Path) -> list[Issue]:
    folder = root / "skills"
    if not folder.is_dir():
        return []
    issues: list[Issue] = []
    found = list(sorted(folder.glob("*/SKILL.md")))
    if not found:
        issues.append(Issue("skills/", "no SKILL.md files"))
        return issues
    for path in found:
        rel = _rel(root, path)
        text = path.read_text(encoding="utf-8")
        if LOCK_HEADING_RE.search(text) is None:
            issues.append(Issue(rel, "missing ## Lock (不绿不能合) heading"))
            continue
        if "sop-lock.md" not in text and "不绿不能合" not in text:
            issues.append(Issue(rel, "Lock section must point at docs/sop-lock.md or 不绿不能合"))
        if not any(name in text for name in ("overlay-check", "sop-lock", "pr-title", "forge check")):
            issues.append(Issue(rel, "Lock section must name overlay-check, sop-lock, pr-title, or forge check"))
    return issues


def check_workshop_docs_and_checks(root: Path) -> list[Issue]:
    if not is_workshop_root(root):
        return []
    issues: list[Issue] = []
    lock_doc = root / "docs" / "sop-lock.md"
    if not lock_doc.is_file():
        issues.append(Issue("docs/sop-lock.md", "missing SOP lock inventory"))
    else:
        text = lock_doc.read_text(encoding="utf-8")
        if "机器判定" not in text or "不绿" not in text:
            issues.append(Issue("docs/sop-lock.md", "must state the 不绿不能合 / 机器判定 principle"))
        if "human-only" not in text and "仅人审" not in text:
            issues.append(Issue("docs/sop-lock.md", "must list human-only (cannot machine-lock) rows"))
        if "forge check" not in text:
            issues.append(Issue("docs/sop-lock.md", "must document python -m forge check as 代推锁"))
    forge_yaml = root / "forge.yaml"
    if not forge_yaml.is_file():
        issues.append(Issue("forge.yaml", "missing workshop forge.yaml"))
    else:
        raw = forge_yaml.read_text(encoding="utf-8")
        missing = [name for name in WORKSHOP_REQUIRED_CHECKS if name not in raw]
        if missing:
            issues.append(Issue("forge.yaml", "required_checks must list " + ", ".join(missing)))
        cr_only = [line for line in raw.splitlines() if "required_checks" in line or line.strip().startswith("- ")]
        names = [line.split("-", 1)[1].strip() for line in raw.splitlines() if line.strip().startswith("- ")]
        check_names = [name for name in names if name in raw]
        non_cr = [name for name in check_names if "coderabbit" not in name.lower()]
        if any("coderabbit" in name.lower() for name in check_names) and not non_cr:
            issues.append(Issue("forge.yaml", "CodeRabbit must not be the only required check"))
        del cr_only
    pr_title = root / ".github" / "workflows" / "pr-title.yml"
    if not pr_title.is_file():
        issues.append(Issue(".github/workflows/pr-title.yml", "missing pr-title workflow"))
    else:
        text = pr_title.read_text(encoding="utf-8")
        if "pull_request" not in text:
            issues.append(Issue(_rel(root, pr_title), "must run on pull_request"))
        if re.search(r"(?m)^  push:", text):
            issues.append(Issue(_rel(root, pr_title), "must not run on push"))
    sop_wf = root / ".github" / "workflows" / "sop-lock.yml"
    if not sop_wf.is_file():
        issues.append(Issue(".github/workflows/sop-lock.yml", "missing sop-lock workflow"))
    else:
        text = sop_wf.read_text(encoding="utf-8")
        if "name: sop-lock" not in text or "python -m forge sop-lock" not in text:
            issues.append(
                Issue(_rel(root, sop_wf), "must be the sop-lock check running python -m forge sop-lock")
            )
    for name in ("dev-pr", "use-forge"):
        skill = root / "skills" / name / "SKILL.md"
        rel = _rel(root, skill)
        if not skill.is_file():
            issues.append(Issue(rel, "missing skill"))
            continue
        text = skill.read_text(encoding="utf-8")
        if "python -m forge check" not in text:
            issues.append(Issue(rel, "must require python -m forge check before submit (代推锁)"))
        if "FORGE_SUBMIT_TOKEN" not in text:
            issues.append(Issue(rel, "must name FORGE_SUBMIT_TOKEN for agent submit"))
    overlay_check = root / ".github" / "workflows" / "overlay-check.yml"
    if overlay_check.is_file():
        data = _load_workflow(overlay_check)
        if data is not None:
            for script in _collect_runs(data):
                if GENERATE_RUN_RE.search(script):
                    issues.append(Issue(_rel(root, overlay_check), "overlay-check must not run generate"))
    manage = root / "skills" / "manage-repo" / "SKILL.md"
    if manage.is_file():
        text = manage.read_text(encoding="utf-8")
        if "合入" not in text or "代推" not in text:
            issues.append(
                Issue(_rel(root, manage), "must distinguish CI 合入锁 from local 代推锁")
            )
        missing = [name for name in WORKSHOP_REQUIRED_CHECKS if name not in text]
        if missing:
            issues.append(
                Issue(_rel(root, manage), "must name required checks " + ", ".join(missing))
            )
    return issues


def check_submit_source(root: Path) -> list[Issue]:
    submit = root / "forge" / "submit.py"
    if not submit.is_file():
        return []
    issues: list[Issue] = []
    text = submit.read_text(encoding="utf-8")
    rel = _rel(root, submit)
    if "run_check" not in text:
        issues.append(Issue(rel, "submit must refuse when forge check is red"))
    if "FORGE_SUBMIT_TOKEN" not in text:
        issues.append(Issue(rel, "submit must require FORGE_SUBMIT_TOKEN"))
    if re.search(r"""\.get\(\s*['\"]GITHUB_TOKEN['\"]""", text):
        issues.append(Issue(rel, "submit must not read GITHUB_TOKEN"))
    if re.search(r"""\.get\(\s*['\"]FORGE_GITHUB_TOKEN['\"]""", text):
        issues.append(Issue(rel, "submit must not read FORGE_GITHUB_TOKEN (Ops apply)"))
    if "resolve_token(" in text:
        issues.append(Issue(rel, "submit must not call apply.resolve_token"))
    return issues


def collect_issues(root: Path) -> list[Issue]:
    root = root.resolve()
    issues: list[Issue] = []
    issues.extend(check_workflows(root))
    issues.extend(check_kernel(root))
    issues.extend(check_husky(root))
    issues.extend(check_skills(root))
    issues.extend(check_submit_source(root))
    issues.extend(check_workshop_docs_and_checks(root))
    issues.sort(key=lambda item: (item.path, item.message))
    return issues


def run_sop_lock(
    root: Path,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    issues = collect_issues(root)
    if issues:
        for issue in issues:
            print(issue, file=err)
        print(f"forge sop-lock: {len(issues)} issue(s)", file=err)
        return EXIT_SOP
    print("forge sop-lock: ok", file=out)
    return EXIT_OK
