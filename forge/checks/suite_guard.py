"""suite_guard row: agent branches must not set or clear blocked."""

from __future__ import annotations

from pathlib import Path

from forge.checks.base import NEED_FORGE_YAML, NEED_GIT, CheckContext, Step
from forge.gitutil import matching_agent_prefix, no_base_detail, normalize_repo_path, run_git


def is_suite_yaml(path: str) -> bool:
    rel = normalize_repo_path(path)
    return rel.startswith("suites/") and rel.endswith("/suite.yaml")


def suite_status(text: str | None) -> str:
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


def show_at(root: Path, base: str, rel: str) -> str | None:
    # ./ makes the path relative to --root even when root is a repo subdirectory.
    proc = run_git(root, "show", f"{base}:./{rel}")
    return proc.stdout if proc.returncode == 0 else None


class SuiteGuard:
    """Agent branches must not set or clear blocked. Humans are recorded.

    An unnamed branch (detached HEAD, no CI env) is an agent: fail closed.
    """

    name = "suite_guard"
    needs = frozenset({NEED_FORGE_YAML, NEED_GIT})

    def applies(self, ctx: CheckContext) -> str | None:
        return None

    def run(self, ctx: CheckContext) -> Step:
        config = ctx.config
        assert config is not None
        if ctx.changed is None:
            return Step(self.name, "skip", "no git work tree")
        resolved = ctx.branch
        prefix = matching_agent_prefix(resolved, config.agent_branch_prefixes)
        if resolved and not prefix:
            return Step(
                self.name,
                "ok",
                f"human branch {resolved}; status changes are reviewed, not blocked",
            )
        branch = resolved or "(detached HEAD, unnamed)"
        if not ctx.base_ref:
            return Step(self.name, "fail", f"agent branch {branch}: {no_base_detail(config.protect)}")
        base = ctx.base_commit
        suites = [path for path in ctx.changed if is_suite_yaml(path)]
        if not suites:
            return Step(self.name, "ok", f"no suite.yaml changed; agent branch {branch}")
        hits: list[str] = []
        for rel in suites:
            new_path = ctx.root / rel
            new_text = new_path.read_text(encoding="utf-8") if new_path.is_file() else None
            old_text = show_at(ctx.root, base, rel) if base else None
            new_present = new_text is not None
            old_present = old_text is not None
            new_status = suite_status(new_text) or ("active" if new_present else "")
            old_status = suite_status(old_text) or ("active" if old_present else "")
            if new_status == "blocked" and old_status != "blocked":
                hits.append(f"{rel} (status {old_status or 'none'} -> blocked)")
            elif old_status == "blocked" and new_status != "blocked":
                shown = new_status or "deleted"
                hits.append(f"{rel} (status blocked -> {shown})")
        if hits:
            return Step(
                self.name,
                "fail",
                "agent branch "
                f"{branch} must not set or clear blocked: {', '.join(hits)}; a human writes that status",
            )
        return Step(
            self.name, "ok", f"suite.yaml edits do not introduce blocked; agent branch {branch}"
        )
