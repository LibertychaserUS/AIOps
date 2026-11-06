"""docs_sync row: forge.yaml docs_sync table + markdown links + pin mentions + STATE.md."""

from __future__ import annotations

import re
from pathlib import Path

from forge.checks.base import (
    NEED_FORGE_YAML,
    NEED_GIT,
    CheckContext,
    Step,
    is_workshop_root,
)
from forge.gitutil import git_paths, is_git_work_tree, no_base_detail, normalize_repo_path, run_git
from forge.pathmatch import path_matches_pattern
from forge.status import state_is_fresh

TAG_MENTION_RE = re.compile(r"(overlay|forge)-v(\d+\.\d+\.\d+)")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def git_tags(root: Path) -> set[str]:
    proc = run_git(root, "tag", "-l")
    if proc.returncode != 0:
        return set()
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def changelog_headings(root: Path) -> set[str]:
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


def markdown_files(root: Path) -> list[Path]:
    """Tracked + unignored *.md under root (git ls-files); falls back to rglob outside git."""
    if is_git_work_tree(root):
        listed = git_paths(
            root, "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.md", "**/*.md"
        )
        if listed is not None:
            seen: set[str] = set()
            out: list[Path] = []
            for rel in listed:
                if rel and rel not in seen and (root / rel).is_file():
                    seen.add(rel)
                    out.append(root / rel)
            return sorted(out)
    return sorted(p for p in root.rglob("*.md") if ".git" not in p.parts)


def relative_link_failures(root: Path) -> list[str]:
    failures: list[str] = []
    for path in markdown_files(root):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in LINK_RE.finditer(text):
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


def pin_mention_failures(root: Path) -> list[str]:
    tags = git_tags(root)
    headings = changelog_headings(root)
    failures: list[str] = []
    for path in markdown_files(root):
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
            failures.append(
                f"{rel} mentions {tag} (not a git tag and not ## [{heading}] in CHANGELOG.md)"
            )
    return failures


class DocsSync:
    name = "docs_sync"
    needs = frozenset({NEED_FORGE_YAML, NEED_GIT})

    def applies(self, ctx: CheckContext) -> str | None:
        return None

    def run(self, ctx: CheckContext) -> Step:
        config = ctx.config
        assert config is not None
        root = ctx.root
        misses: list[str] = []
        if ctx.changed is not None:
            if config.docs_sync and not ctx.base_ref:
                misses.append(no_base_detail(config.protect))
            changed = ctx.changed if ctx.base_ref else ()
            for rule in config.docs_sync:
                if any(path_matches_pattern(path, pattern) for path in changed for pattern in rule.paths):
                    if not any(normalize_repo_path(req) in changed for req in rule.require):
                        misses.append(
                            "changed "
                            + ", ".join(rule.paths)
                            + " but missing "
                            + ", ".join(rule.require)
                        )
        misses.extend(relative_link_failures(root))
        if is_workshop_root(root):
            # overlay-v*/forge-v* tags live in the tool repo; adopters may cite them freely.
            misses.extend(pin_mention_failures(root))
        state_path = root / "docs" / "STATE.md"
        if state_path.is_file():
            ok, message = state_is_fresh(root, config, state_path.read_text(encoding="utf-8"))
            if not ok:
                misses.append(message)
        if misses:
            shown = "; ".join(misses[:8])
            extra = f" (+{len(misses) - 8} more)" if len(misses) > 8 else ""
            return Step(self.name, "fail", shown + extra)
        return Step(self.name, "ok", "table + links + pins")
