"""Lint a GitHub PR body against docs/pr-brief.md headings. No GitHub write."""

from __future__ import annotations

import re
from pathlib import Path

from forge import EXIT_OK

EXIT_BRIEF = 2

REQUIRED_H2 = (
    "做了什么",
    "为什么",
    "动了哪些门",
    "怎么验",
    "不做什么",
    "分工",
)

H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
BRIEF_REL = Path("docs") / "pr-brief.md"


def brief_spec_exists(root: Path) -> bool:
    return (root / BRIEF_REL).is_file()


def lint_pr_body(body: str | None) -> tuple[int, str]:
    """Return (0, '') or (2, reason). Headings must appear as ## and in order."""
    if body is None:
        return EXIT_BRIEF, "PR body is missing; need six ## headings from docs/pr-brief.md"
    text = body.replace("\r\n", "\n")
    if text.strip() == "":
        return EXIT_BRIEF, "PR body is empty; need six ## headings from docs/pr-brief.md"
    found = [match.group(1).strip() for match in H2_RE.finditer(text)]
    missing = [heading for heading in REQUIRED_H2 if heading not in found]
    if missing:
        return EXIT_BRIEF, "PR body missing headings: " + ", ".join(missing)
    indices = [found.index(heading) for heading in REQUIRED_H2]
    if indices != sorted(indices):
        return EXIT_BRIEF, "PR body headings are out of order (docs/pr-brief.md)"
    return EXIT_OK, ""
