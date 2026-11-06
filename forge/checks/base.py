"""Shared shapes for forge check steps: Step, CheckContext, the Check protocol.

Check modules import from here, never from ``forge.checks`` itself (the
package ``__init__`` imports them to build the ordered ``CHECKS`` tuple).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO

from forge.config import ForgeConfig
from forge.title import SpecRef

EXIT_CHECK = 2

# A check's ``applies`` returns this when the row must not be printed at all on
# this root (workshop-only steps on an adopter root). Any other string is a
# visible skip reason.
HIDDEN = "hidden: not a step on this root"

# What the runner guarantees before ``run`` is called (see forge.check.run_one).
NEED_FORGE_YAML = "forge.yaml"  # no forge.yaml -> skip; unloadable -> fail
NEED_GIT = "git"  # git missing -> fail with the GitUnavailable message
NEED_BASE = "base"  # ok without a visible base -> fail closed (no_base_detail)
KNOWN_NEEDS = frozenset({NEED_FORGE_YAML, NEED_GIT, NEED_BASE})

OverlayFn = Callable[[Path, TextIO, TextIO], int]
SchemaFn = Callable[[Path, TextIO, TextIO], int]
UnittestFn = Callable[[Path, Sequence[str], TextIO, TextIO], int]


@dataclass(frozen=True)
class Step:
    name: str
    status: str  # ok | fail | skip
    detail: str = ""


@dataclass(frozen=True)
class CheckContext:
    """Everything a check may read. Built once per ``forge check`` run.

    config is None with config_error None when there is no forge.yaml;
    config_error carries the ForgeError message when it does not load.
    git_error is the GitUnavailable message when git is not on PATH; then
    branch / base / changed are None. changed is None outside a git work tree.
    base_ref None means the protect base is not visible (fail closed).
    """

    root: Path
    config: ForgeConfig | None
    config_error: str | None
    env: Mapping[str, str]
    branch: str | None
    base_ref: str | None
    base_commit: str | None
    changed: tuple[str, ...] | None
    title_ref: SpecRef
    body_ref: SpecRef
    head_branch: str | None
    run_unittests: bool
    git_error: str | None
    out: TextIO
    err: TextIO
    overlay_validate: OverlayFn | None = None
    overlay_cover: OverlayFn | None = None
    schema_runner: SchemaFn | None = None
    unittest_runner: UnittestFn | None = None


class Check(Protocol):
    """One checklist row. ``needs`` names the runner disciplines it inherits."""

    name: str
    needs: frozenset[str]

    def applies(self, ctx: CheckContext) -> str | None:
        """None to run; a skip reason to print a skip row; HIDDEN to print nothing."""

    def run(self, ctx: CheckContext) -> Step: ...


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


def last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def print_captured(text: str, stream: TextIO) -> None:
    if not text:
        return
    if text.endswith("\n"):
        print(text, file=stream, end="")
    else:
        print(text, file=stream)
