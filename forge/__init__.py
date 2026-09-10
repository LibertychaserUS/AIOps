"""Forge: install GitHub collaboration policy via repository Rulesets."""

from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"

PACKAGE_DIR = Path(__file__).resolve().parent
RULESET_JSON = PACKAGE_DIR / "ruleset.protected-default.json"
RULESET_NAME = "forge-protected-default"
SCHEMA_ID = "forge-config/v1"

EXIT_OK = 0
EXIT_AUTH = 2
EXIT_CONFIG = 3
EXIT_API = 4

# Apply must never target the Learning Guide product repo (fixture, not a test sink).
FORBIDDEN_REPOS = frozenset(
    {
        "first-light-techhk/learningguideportal",
    }
)

COPY_FILES_NOTE = (
    "copy these files:\n"
    "  forge/agent-policy.md -> AGENTS.md\n"
    "  forge/CODEOWNERS.example -> .github/CODEOWNERS"
)
