"""Forge: install GitHub collaboration policy via repository Rulesets."""

from __future__ import annotations

from pathlib import Path

__version__ = "1.1.0"

PACKAGE_DIR = Path(__file__).resolve().parent
RULESET_JSON = PACKAGE_DIR / "ruleset.protected-default.json"
SCHEMA_ID = "forge-config/v1"
TAG_RULESET_NAME = "forge-protected-tags"
DEFAULT_TAG_PATTERNS = ("overlay-v*", "forge-v*")

EXIT_OK = 0
EXIT_AUTH = 2
EXIT_CONFIG = 3
EXIT_API = 4

# Dev/agent 代推 only. Not Ops apply. Not CI workflow GITHUB_TOKEN.
SUBMIT_TOKEN_ENV = "FORGE_SUBMIT_TOKEN"

# Submit must never open PRs on the Learning Guide upstream (fixture, not a test sink).
FORBIDDEN_REPOS = frozenset(
    {
        "first-light-techhk/learningguideportal",
    }
)


def branch_ruleset_name(branch: str) -> str:
    return f"forge-protected-{branch}"

COPY_FILES_NOTE = (
    "copy these files:\n"
    "  forge/agent-policy.md -> AGENTS.md\n"
    "  forge/CODEOWNERS.example -> .github/CODEOWNERS"
)
