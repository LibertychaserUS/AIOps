"""The closed `forge check` registry (ADR 0009).

CHECKS is an explicit, ordered tuple: the checklist prints in this order, and
deny_paths / suite_guard share one diff, pr-title / pr-body one event decision.
No dynamic discovery of any kind (no module loader, no package scan, no
plugin metadata): adding a check is one module here, one entry below, one
test, one docs row. sop-lock asserts this file stays that way.
"""

from __future__ import annotations

from forge.checks.base import (
    HIDDEN,
    KNOWN_NEEDS,
    NEED_BASE,
    NEED_FORGE_YAML,
    NEED_GIT,
    Check,
    CheckContext,
    Step,
)
from forge.checks.deny_paths import DenyPaths
from forge.checks.docs_sync import DocsSync
from forge.checks.overlay import OverlayCover, OverlayValidate
from forge.checks.schema import SchemaCheck
from forge.checks.sop_lock import SopLock
from forge.checks.spec import PrBody, PrTitle
from forge.checks.suite_guard import SuiteGuard
from forge.checks.unittest_ import Unittest

CHECKS: tuple[Check, ...] = (
    OverlayValidate(),
    OverlayCover(),
    PrTitle(),
    PrBody(),
    DenyPaths(),
    SuiteGuard(),
    DocsSync(),
    SopLock(),
    SchemaCheck(),
    Unittest(),
)

__all__ = [
    "CHECKS",
    "HIDDEN",
    "KNOWN_NEEDS",
    "NEED_BASE",
    "NEED_FORGE_YAML",
    "NEED_GIT",
    "Check",
    "CheckContext",
    "Step",
]
