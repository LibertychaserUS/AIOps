"""Grep-driven lock: v1 Overlay terms and product accent stay out of canonical docs."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Spec §3 allow-list.
SKIP_DIR_PARTS = {
    "examples/learning-guide",
    "docs/history",
    "docs/adr",
    ".git",
}

SKIP_FILES = {
    "CHANGELOG.md",
    # Generated from current argparse until W1/W2 land; integrator regenerates.
    "docs/cli.md",
    # Migration must name old tokens; same class as CHANGELOG / ADR.
    "docs/migration-v2.md",
}

# W1 Overlay / W2 Forge own these until merge. Hits are leftover, not this test's red.
W12_PREFIXES = (
    "skills/",
    ".agents/skills/",
    ".cursor/skills/",
    ".claude/skills/",
    "inbox/",
    "suites/",
    "schema/",
)

TERM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("armed", re.compile(r"\barmed\b")),
    ("reviewed_by", re.compile(r"reviewed_by")),
    ("LearningGuidePortal", re.compile(r"LearningGuidePortal")),
    ("ilovelearningguide", re.compile(r"ilovelearningguide", re.IGNORECASE)),
    ("Verify", re.compile(r"\bVerify\b")),
    ("--agent copilot", re.compile(r"--agent copilot")),
    ("releases/tag/", re.compile(r"releases/tag/")),
)

SKILL_GLOB = ("skills",)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _skipped_dir(rel: str) -> bool:
    for part in SKIP_DIR_PARTS:
        if rel == part or rel.startswith(part + "/"):
            return True
    return False


def _is_w12(rel: str) -> bool:
    return False  # integration done: every file is owned


def _armed_only_adr_filename(line: str) -> bool:
    if "0002-remove-armed" not in line:
        return False
    stripped = line.replace("0002-remove-armed", "")
    return re.search(r"\barmed\b", stripped) is None


def iter_targets() -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = _rel(path)
        if _skipped_dir(rel) or rel in SKIP_FILES:
            continue
        if path.suffix == ".md":
            out.append(path)
            continue
        if rel.startswith("skills/"):
            out.append(path)
    return out


MIGRATION_MARKERS = ("migrate", "删除 `", "已移除", "已删除", "旧值", "旧 `", "旧字段", "v1 →", "→ `active`")


def _is_migration_line(line: str) -> bool:
    """Contract / migration docs must name the removed fields to reject them."""
    return any(marker in line for marker in MIGRATION_MARKERS)


def collect_hits() -> tuple[list[str], list[str]]:
    owned: list[str] = []
    leftover: list[str] = []
    for path in iter_targets():
        rel = _rel(path)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, pattern in TERM_PATTERNS:
                if pattern.search(line) is None:
                    continue
                if name == "armed" and _armed_only_adr_filename(line):
                    continue
                if name in {"armed", "reviewed_by"} and _is_migration_line(line):
                    continue
                item = f"{rel}:{lineno}: {name}: {line.strip()}"
                if _is_w12(rel):
                    leftover.append(item)
                else:
                    owned.append(item)
    return owned, leftover


class NoStaleTermsTests(unittest.TestCase):
    def test_owned_docs_have_no_stale_terms(self) -> None:
        owned, leftover = collect_hits()
        self.assertEqual(
            owned,
            [],
            "stale terms in W3-owned files:\n" + "\n".join(owned[:80]),
        )
        # leftover is reported in /tmp/audit/w3-docs-report.md; do not fail.
        self.assertIsInstance(leftover, list)
