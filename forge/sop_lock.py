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

WORKSHOP_REQUIRED_CHECKS = ("overlay-check", "pr-title", "forge-check", "sop-lock", "unittest")
COMMON_CHECKS = ("pr-title", "sop-lock")
LOCK_HEADING_RE = re.compile(r"^## Lock\b", re.MULTILINE)
GENERATE_RUN_RE = re.compile(
    r"(python[0-9.]*\s+-m\s+overlay\s+generate)|(\boverlay\s+generate\b)",
    re.IGNORECASE,
)
UNITTEST_RE = re.compile(r"unittest\s+discover")
FORGE_UNITTEST_RE = re.compile(r"unittest\s+discover\s+-s\s+tests/forge\b")
SUBMIT_RUN_RE = re.compile(r"python[0-9.]*\s+-m\s+forge\s+submit")
CI_SELECT_RE = re.compile(r"python[0-9.]*\s+-m\s+forge\s+ci-select")
FORGE_CHECK_RUN_RE = re.compile(r"python[0-9.]*\s+-m\s+forge\s+check\b")
PINNED_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
# v4, v4.1, v4.1.0, overlay-v2.0.0, forge-v1.1.3 (optional -rc.1 / +build suffix).
VERSION_TAG_RE = re.compile(r"^(?:[A-Za-z0-9_.]+(?:-[A-Za-z0-9_.]+)*-)?v[0-9]+(?:\.[0-9]+){0,2}(?:[-+][0-9A-Za-z.-]+)?$")
LOCKED_CI_JOBS = ("pr-title", "sop-lock", "unittest")
PR_TITLE_IF_RE = re.compile(r"^github\.event_name\s*==\s*'pull_request'$")
FAIL_OPEN_RUN_RES = (
    (re.compile(r"\|\|\s*(?:true\b|:(?=\s|;|$)|exit\s+0\b)"), "|| true"),
    (re.compile(r";\s*exit\s+0\b"), "; exit 0"),
    (re.compile(r"\bset\s+\+e\b"), "set +e"),
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


def floating_uses_ref(uses: str) -> str | None:
    """Return the offending ref when `uses:` is not pinned to a SHA or version tag."""
    text = uses.strip()
    if text.startswith("./") or text.startswith("docker://"):
        return None
    if "@" not in text:
        return "(no ref)"
    ref = text.rsplit("@", 1)[1].strip()
    if PINNED_SHA_RE.fullmatch(ref) or VERSION_TAG_RE.fullmatch(ref):
        return None
    return ref or "(no ref)"


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


def _has_path_filter(on_field: Any) -> bool:
    if not isinstance(on_field, dict):
        return False
    for value in on_field.values():
        if isinstance(value, dict) and "paths" in value:
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


def _is_forge_unit_layer(path: Path, data: dict[str, Any], script: str) -> bool:
    """Forge product CI may discover tests/forge. That is not an Overlay select bypass."""
    name = str(data.get("name") or "")
    filename = path.name
    forge_file = filename in {"forge-check.yml", "forge-check.yaml"}
    forge_named = name == "forge-check"
    return (forge_file or forge_named) and bool(FORGE_UNITTEST_RE.search(script))


def _is_ci_unittest_job(path: Path, job_id: str) -> bool:
    return path.name in {"ci.yml", "ci.yaml"} and job_id == "unittest"


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
            bypass: list[str] = []
            jobs = data.get("jobs")
            if isinstance(jobs, dict):
                for job_id, job in jobs.items():
                    for script in _job_runs(job):
                        if not UNITTEST_RE.search(script):
                            continue
                        if _is_forge_unit_layer(path, data, script):
                            continue
                        if _is_ci_unittest_job(path, str(job_id)):
                            continue
                        bypass.append(script)
            if bypass:
                issues.append(
                    Issue(
                        rel,
                        "do not add a unittest workflow that bypasses Overlay select "
                        "(Overlay tests stay in an Overlay product_command; "
                        "Forge tests stay on forge-check; workshop full discover is ci.yml job unittest)",
                    )
                )
        for ref in uses:
            for banned in BANNED_USES_RE:
                if banned.search(ref):
                    issues.append(
                        Issue(rel, f"must not workflow_call product ci.yml / Verify ({ref})")
                    )
                    break
            floating = floating_uses_ref(ref)
            if floating is not None:
                issues.append(
                    Issue(rel, f"uses: must pin a version tag or 40-hex SHA, not {floating} ({ref})")
                )
        for script in runs:
            if SUBMIT_RUN_RE.search(script):
                issues.append(
                    Issue(rel, "CI must not call forge submit (GITHUB_TOKEN is 合入锁, not 代推)")
                )
                break
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
        if not any(
            name in text
            for name in ("overlay-check", "sop-lock", "pr-title", "forge-check", "forge check")
        ):
            issues.append(
                Issue(
                    rel,
                    "Lock section must name overlay-check, sop-lock, pr-title, forge-check, or forge check",
                )
            )
    return issues


def _job_runs(job: Any) -> list[str]:
    return _collect_runs(job) if isinstance(job, dict) else []


COMMON_LEFTOVER_WORKFLOWS = ("pr-title.yml", "sop-lock.yml")


def _is_pull_request_only(when: Any) -> bool:
    if not isinstance(when, str):
        return False
    text = when.strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    text = " ".join(text.replace('"', "'").split())
    return PR_TITLE_IF_RE.fullmatch(text) is not None


def _fail_open_issues(rel: str, job_id: str, job: dict[str, Any]) -> list[Issue]:
    """Locked jobs must be able to go red: no continue-on-error, no swallowed exit codes."""
    issues: list[Issue] = []
    steps = job.get("steps") if isinstance(job.get("steps"), list) else []
    holders: list[Any] = [job, *steps]
    if any(
        isinstance(item, dict) and item.get("continue-on-error", False) is not False
        for item in holders
    ):
        issues.append(Issue(rel, f"{job_id} job must not set continue-on-error"))
    for script in _job_runs(job):
        for pattern, label in FAIL_OPEN_RUN_RES:
            if pattern.search(script):
                issues.append(Issue(rel, f"{job_id} job run must not swallow failures ({label})"))
    return issues


def _check_workshop_ci(root: Path) -> list[Issue]:
    """Common checks live in ci.yml. Product doors stay in their own files."""
    path = root / ".github" / "workflows" / "ci.yml"
    rel = _rel(root, path)
    issues: list[Issue] = []
    for leftover in COMMON_LEFTOVER_WORKFLOWS:
        extra = root / ".github" / "workflows" / leftover
        if extra.is_file():
            issues.append(
                Issue(
                    _rel(root, extra),
                    "common checks live in ci.yml; delete leftover " + leftover,
                )
            )
    if not path.is_file():
        issues.append(Issue(rel, "missing ci.yml for common checks (jobs pr-title + sop-lock + unittest)"))
        return issues
    text = path.read_text(encoding="utf-8")
    data = _load_workflow(path)
    on_field = (data or {}).get("on") or (data or {}).get(True)
    if _has_path_filter(on_field):
        issues.append(Issue(rel, "must not path-filter on: (workflow must start; skip jobs with success)"))
    if not _on_has(on_field, "pull_request"):
        issues.append(Issue(rel, "must run on pull_request"))
    jobs = (data or {}).get("jobs")
    if not isinstance(jobs, dict):
        issues.append(Issue(rel, "ci.yml must define jobs"))
        return issues
    for job_id in LOCKED_CI_JOBS:
        job = jobs.get(job_id)
        if not isinstance(job, dict):
            issues.append(Issue(rel, f"must have job {job_id}"))
            continue
        if str(job.get("name") or job_id) != job_id:
            issues.append(Issue(rel, f"must keep check name {job_id}"))
        issues.extend(_fail_open_issues(rel, job_id, job))
        runs = _job_runs(job)
        if any(CI_SELECT_RE.search(script) for script in runs):
            issues.append(Issue(rel, f"common {job_id} must always run (no ci-select skip)"))
        if job_id == "pr-title":
            if not _is_pull_request_only(job.get("if")):
                issues.append(
                    Issue(rel, "pr-title job if: must be exactly github.event_name == 'pull_request'")
                )
            if not any("python -m forge pr-title" in script for script in runs):
                issues.append(Issue(rel, "pr-title job must run python -m forge pr-title"))
        else:
            if "if" in job:
                issues.append(Issue(rel, f"{job_id} job must not have if: (it always runs)"))
            if job_id == "sop-lock" and not any(
                "python -m forge sop-lock" in script for script in runs
            ):
                issues.append(Issue(rel, "sop-lock job must run python -m forge sop-lock"))
            if job_id == "unittest" and not any(UNITTEST_RE.search(script) for script in runs):
                issues.append(Issue(rel, "unittest job must run python3 -m unittest discover"))
    if SUBMIT_RUN_RE.search(text):
        issues.append(Issue(rel, "must not call forge submit"))
    if GENERATE_RUN_RE.search(text):
        issues.append(Issue(rel, "must not run overlay generate"))
    return issues


def _check_product_workflow(root: Path, filename: str, check_name: str) -> list[Issue]:
    path = root / ".github" / "workflows" / filename
    rel = _rel(root, path)
    if not path.is_file():
        return [Issue(rel, f"missing {check_name} workflow")]
    text = path.read_text(encoding="utf-8")
    data = _load_workflow(path)
    issues: list[Issue] = []
    if f"name: {check_name}" not in text:
        issues.append(Issue(rel, f"must be the {check_name} check"))
    if not CI_SELECT_RE.search(text):
        issues.append(Issue(rel, f"must call python -m forge ci-select --check {check_name}"))
    on_field = (data or {}).get("on") or (data or {}).get(True)
    if _has_path_filter(on_field):
        issues.append(
            Issue(
                rel,
                "must not path-filter on: (workflow must start; skip jobs with success)",
            )
        )
    if data is not None:
        for script in _collect_runs(data):
            if SUBMIT_RUN_RE.search(script):
                issues.append(Issue(rel, "must not call forge submit"))
                break
            if GENERATE_RUN_RE.search(script):
                issues.append(Issue(rel, "must not run overlay generate"))
                break
    return issues


def _check_workshop_branch_rules(forge_yaml: Path) -> list[Issue]:
    """Parsed config, not substrings: every protect branch carries the workshop checks."""
    from forge.apply import ForgeError, load_config

    try:
        config = load_config(forge_yaml)
    except ForgeError as exc:
        return [Issue("forge.yaml", f"not loadable: {exc.message}")]
    issues: list[Issue] = []
    for branch in config.protect:
        checks = config.rule_for(branch).required_checks
        missing = [name for name in WORKSHOP_REQUIRED_CHECKS if name not in checks]
        if missing:
            issues.append(
                Issue("forge.yaml", f"branches.{branch}.required_checks must list " + ", ".join(missing))
            )
        if checks and all("coderabbit" in name.lower() for name in checks):
            issues.append(Issue("forge.yaml", "CodeRabbit must not be the only required check"))
    if "main" not in config.protect:
        issues.append(Issue("forge.yaml", "protect must include main"))
    else:
        main = config.rule_for("main")
        if main.approvals < 1:
            issues.append(Issue("forge.yaml", "branches.main.approvals must be >= 1"))
        if not main.code_owners:
            issues.append(Issue("forge.yaml", "branches.main.code_owners must be true"))
    return issues


# Paths CODEOWNERS must cover in the workshop: branch prefix is only a convention
# (`agent/x` renames to `fix-x`); CODEOWNERS + Ruleset `code_owners` is the lock.
# (pattern shown in the message, a representative path that must match)
CODEOWNERS_REQUIRED = (
    ("suites/**", "suites/example/suite.yaml"),
    ("forge.yaml", "forge.yaml"),
    ("overlay.yaml", "overlay.yaml"),
)


def _codeowners_regex(pattern: str) -> str:
    """gitignore-style pattern (as GitHub CODEOWNERS reads it) to a full-path regex."""
    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    body = pattern.strip("/")
    out = ""
    i = 0
    while i < len(body):
        ch = body[i]
        if body.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif body.startswith("**", i):
            out += ".*"
            i += 2
        elif ch == "*":
            out += "[^/]*"
            i += 1
        elif ch == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(ch)
            i += 1
    prefix = "" if anchored else "(?:.*/)?"
    # `dir/` or a bare `dir` owns everything beneath it; `dir/*` only its direct files.
    suffix = "" if body.endswith("*") else "(?:/.*)?"
    return f"^{prefix}{out}{suffix}$"


def codeowners_covers(pattern: str, path: str) -> bool:
    return re.match(_codeowners_regex(pattern), path) is not None


def codeowners_patterns(text: str) -> list[str]:
    """Patterns that name at least one owner (a bare pattern unassigns, it owns nothing)."""
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and any(part.startswith("@") or "@" in part for part in parts[1:]):
            out.append(parts[0])
    return out


def check_codeowners(root: Path) -> list[Issue]:
    """Workshop only: `.github/CODEOWNERS` exists and owns suites/**, forge.yaml, overlay.yaml."""
    if not is_workshop_root(root):
        return []
    path = root / ".github" / "CODEOWNERS"
    rel = ".github/CODEOWNERS"
    if not path.is_file():
        return [Issue(rel, "missing; CODEOWNERS + Ruleset is the agent-identity lock, not the branch prefix")]
    patterns = codeowners_patterns(path.read_text(encoding="utf-8"))
    issues: list[Issue] = []
    for shown, sample in CODEOWNERS_REQUIRED:
        if not any(codeowners_covers(pattern, sample) for pattern in patterns):
            issues.append(Issue(rel, f"must assign an owner to {shown}"))
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
        if "FORGE_SUBMIT_TOKEN" not in text:
            issues.append(Issue("docs/sop-lock.md", "must name FORGE_SUBMIT_TOKEN as the 代推 secret"))
        if "forge-check" not in text:
            issues.append(Issue("docs/sop-lock.md", "must list forge-check as a product gate"))
        if "通用" not in text or "产品门" not in text:
            issues.append(Issue("docs/sop-lock.md", "must state 通用检查 ≠ 产品门"))
        if "ci-select" not in text and "forge.yaml" not in text:
            issues.append(Issue("docs/sop-lock.md", "must document the forge.yaml CI selector"))
        if "封顶" not in text or "换底" not in text or "squash" not in text:
            issues.append(
                Issue("docs/sop-lock.md", "must state squash 封顶 / 换底 as commit 规格化")
            )
    brief = root / "docs" / "pr-brief.md"
    if not brief.is_file():
        issues.append(Issue("docs/pr-brief.md", "missing PR brief spec"))
    else:
        brief_text = brief.read_text(encoding="utf-8")
        if "封顶" not in brief_text or "换底" not in brief_text or "squash" not in brief_text:
            issues.append(
                Issue("docs/pr-brief.md", "must specify squash 封顶 / 换底 (commit 规格化)")
            )
    forge_yaml = root / "forge.yaml"
    if not forge_yaml.is_file():
        issues.append(Issue("forge.yaml", "missing workshop forge.yaml"))
    else:
        raw = forge_yaml.read_text(encoding="utf-8")
        issues.extend(_check_workshop_branch_rules(forge_yaml))
        if "ci:" not in raw or "common:" not in raw or "products:" not in raw:
            issues.append(Issue("forge.yaml", "must declare ci.common and ci.products selector"))
        try:
            from forge.ci_select import PRODUCT_NAMES, load_ci_config

            config = load_ci_config(root)
            extra = [name for name in config.products if name not in PRODUCT_NAMES]
            if extra:
                issues.append(Issue("forge.yaml", "do not invent a third product under ci.products"))
            for name in COMMON_CHECKS:
                if name not in config.common:
                    issues.append(Issue("forge.yaml", f"ci.common must list {name}"))
            for product, check in (("overlay", "overlay-check"), ("forge", "forge-check")):
                gate = config.products.get(product)
                if gate is None or gate.check != check:
                    issues.append(Issue("forge.yaml", f"ci.products.{product}.check must be {check}"))
        except Exception as exc:
            issues.append(Issue("forge.yaml", f"ci selector is not loadable: {exc}"))
    issues.extend(_check_workshop_ci(root))
    issues.extend(_check_product_workflow(root, "forge-check.yml", "forge-check"))
    forge_check = root / ".github" / "workflows" / "forge-check.yml"
    if forge_check.is_file():
        text = forge_check.read_text(encoding="utf-8")
        # `forge check` runs the full discover (covers tests/forge) plus
        # deny_paths / suite_guard / docs_sync; those only held locally before.
        if not FORGE_CHECK_RUN_RE.search(text):
            issues.append(
                Issue(_rel(root, forge_check), "must run python3 -m forge check --root .")
            )
        if "forge apply" not in text or "--dry-run" not in text:
            issues.append(Issue(_rel(root, forge_check), "must run forge apply --dry-run"))
        if "forge status" not in text or "--check-state" not in text:
            issues.append(
                Issue(_rel(root, forge_check), "must run forge status --check-state")
            )
        if "python -m forge sop-lock" in text:
            issues.append(
                Issue(_rel(root, forge_check), "sop-lock is common; do not own it on forge-check")
            )
        if "python -m forge pr-title" in text:
            issues.append(
                Issue(_rel(root, forge_check), "pr-title is common; do not own it on forge-check")
            )
    issues.extend(_check_product_workflow(root, "overlay-check.yml", "overlay-check"))
    overlay_check = root / ".github" / "workflows" / "overlay-check.yml"
    if overlay_check.is_file():
        text = overlay_check.read_text(encoding="utf-8")
        if FORGE_UNITTEST_RE.search(text):
            issues.append(
                Issue(_rel(root, overlay_check), "overlay-check must not run Forge unit tests")
            )
        if "name: spec" not in text or "python -m forge pr-title" not in text:
            issues.append(
                Issue(_rel(root, overlay_check), "Overlay Ops must run PR spec (pr-title) before full CI")
            )
        if "name: review-bots" not in text or "python -m forge ops-review" not in text:
            issues.append(
                Issue(_rel(root, overlay_check), "Overlay Ops must run review-bots after spec")
            )
        if "python -m forge bounce" not in text:
            issues.append(
                Issue(_rel(root, overlay_check), "Overlay Ops must bounce + keep ops-debug on failure")
            )
        if "needs: [select, spec, review-bots]" not in text:
            issues.append(
                Issue(
                    _rel(root, overlay_check),
                    "full Overlay CI must need spec and review-bots (DAG)",
                )
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
            issues.append(
                Issue(rel, "must name FORGE_SUBMIT_TOKEN for agent 代推")
            )
        if "通用" not in text or "产品门" not in text:
            issues.append(Issue(rel, "must state 通用检查 ≠ 产品门"))
        if "封顶" not in text or "换底" not in text:
            issues.append(Issue(rel, "must state squash 封顶 / 换底 (commit 规格化)"))
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
        if "通用" not in text or "产品门" not in text:
            issues.append(Issue(_rel(root, manage), "must state 通用检查 ≠ 产品门"))
        if "封顶" not in text or "换底" not in text:
            issues.append(
                Issue(_rel(root, manage), "must state squash 封顶 / 换底 (commit 规格化)")
            )
    overlay_skill = root / "skills" / "use-overlay" / "SKILL.md"
    if overlay_skill.is_file():
        text = overlay_skill.read_text(encoding="utf-8")
        if "通用" not in text or "产品门" not in text:
            issues.append(Issue(_rel(root, overlay_skill), "must state 通用检查 ≠ 产品门"))
    return issues



_SUBMIT_DOC_NEEDLES = (
    "FORGE_SUBMIT_TOKEN",
    "Forge 不保管",
    "gh auth login",
    "GH_TOKEN",
    "extraheader",
    "OPENAI_API_KEY",
    "GITHUB_TOKEN",
)


def check_submit_custody_docs(root: Path) -> list[Issue]:
    path = root / "docs" / "submit-credential.md"
    if not path.is_file():
        return [
            Issue(
                "docs/submit-credential.md",
                "missing docs/submit-credential.md: 代推锁要求点名 FORGE_SUBMIT_TOKEN",
            )
        ]
    text = path.read_text(encoding="utf-8")
    missing = [n for n in _SUBMIT_DOC_NEEDLES if n not in text]
    if missing:
        return [
            Issue(
                "docs/submit-credential.md",
                "docs/submit-credential.md missing custody needles: " + ", ".join(missing),
            )
        ]
    return []


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
        issues.append(
            Issue(rel, "submit must require FORGE_SUBMIT_TOKEN (no silent gh / GITHUB_TOKEN fallback)")
        )
    if "封顶" not in text or "protect" not in text:
        issues.append(Issue(rel, "submit base must be protect (squash 封顶)"))
    if re.search(r"""\.get\(\s*['\"]GITHUB_TOKEN['\"]""", text):
        issues.append(Issue(rel, "submit must not read GITHUB_TOKEN"))
    if re.search(r"""\.get\(\s*['\"]FORGE_GITHUB_TOKEN['\"]""", text):
        issues.append(Issue(rel, "submit must not read FORGE_GITHUB_TOKEN (Ops apply)"))
    if "resolve_token(" in text:
        issues.append(Issue(rel, "submit must not call apply.resolve_token"))
    cred = root / "forge" / "credential.py"
    if cred.is_file():
        cred_text = cred.read_text(encoding="utf-8")
        if "FORGE_SUBMIT_TOKEN" not in cred_text:
            issues.append(
                Issue(
                    _rel(root, cred),
                    "credential.py must treat FORGE_SUBMIT_TOKEN as the only write credential",
                )
            )
        if 'source="gh-login"' in cred_text or "source='gh-login'" in cred_text:
            issues.append(
                Issue(
                    _rel(root, cred),
                    "credential.py must not treat ambient gh auth as a valid submit credential",
                )
            )
    return issues


DISCOVERY_SKILL_DIRS = (".agents/skills", ".cursor/skills", ".claude/skills")


def check_skill_discovery(root: Path) -> list[Issue]:
    """Codex=.agents/skills, Cursor=.cursor/skills, Claude Code=.claude/skills."""
    if not is_workshop_root(root):
        return []
    canonical = root / "skills"
    names = sorted(path.name for path in canonical.iterdir() if (path / "SKILL.md").is_file())
    issues: list[Issue] = []
    if not names:
        issues.append(Issue("skills/", "no SKILL.md packages to expose"))
        return issues
    for rel in DISCOVERY_SKILL_DIRS:
        folder = root / rel
        if not folder.is_dir():
            issues.append(Issue(rel, "missing native skill discovery directory"))
            continue
        for name in names:
            link = folder / name
            if not link.exists():
                issues.append(Issue(f"{rel}/{name}", "must point at skills/" + name))
                continue
            target = (canonical / name).resolve()
            try:
                resolved = link.resolve()
            except OSError:
                issues.append(Issue(f"{rel}/{name}", "cannot resolve skill path"))
                continue
            if resolved != target:
                issues.append(Issue(f"{rel}/{name}", f"must resolve to skills/{name}"))
    return issues


def check_release_workflow(root: Path) -> list[Issue]:
    if not is_workshop_root(root):
        return []
    path = root / ".github" / "workflows" / "release.yml"
    rel = _rel(root, path)
    if not path.is_file():
        return [Issue(rel, "missing release workflow (publish product tags, not production CD)")]
    issues: list[Issue] = []
    text = path.read_text(encoding="utf-8")
    data = _load_workflow(path)
    on_field = (data or {}).get("on") or (data or {}).get(True)
    if not _on_has(on_field, "workflow_dispatch"):
        issues.append(Issue(rel, "release must be workflow_dispatch (human publish)"))
    if _on_has(on_field, "push"):
        issues.append(Issue(rel, "release must not run on push"))
    if not re.search(r"python[0-9.]*\s+-m\s+forge\s+release", text):
        issues.append(Issue(rel, "must call python -m forge release"))
    if SUBMIT_RUN_RE.search(text):
        issues.append(Issue(rel, "must not call forge submit"))
    if GENERATE_RUN_RE.search(text):
        issues.append(Issue(rel, "must not run overlay generate"))
    lock = root / "docs" / "release.md"
    if not lock.is_file():
        issues.append(Issue("docs/release.md", "missing publish SOP (two product tags, not production CD)"))
    else:
        doc = lock.read_text(encoding="utf-8")
        if "overlay-v" not in doc or "forge-v" not in doc:
            issues.append(Issue("docs/release.md", "must name overlay-v* and forge-v*"))
        if "workflow_dispatch" not in doc or "生产" not in doc:
            issues.append(Issue("docs/release.md", "must say dispatch-only and 不打生产"))
    return issues


def collect_issues(root: Path) -> list[Issue]:
    root = root.resolve()
    issues: list[Issue] = []
    issues.extend(check_workflows(root))
    issues.extend(check_kernel(root))
    issues.extend(check_husky(root))
    issues.extend(check_skills(root))
    issues.extend(check_skill_discovery(root))
    issues.extend(check_submit_source(root))
    if is_workshop_root(root):
        issues.extend(check_submit_custody_docs(root))
        issues.extend(check_release_workflow(root))
        issues.extend(check_codeowners(root))
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
