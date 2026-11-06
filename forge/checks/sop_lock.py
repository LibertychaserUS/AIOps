"""sop-lock row: workshop root only (adopters never see it)."""

from __future__ import annotations

import io

from forge import EXIT_OK
from forge.checks.base import (
    HIDDEN,
    CheckContext,
    Step,
    is_workshop_root,
    last_line,
    print_captured,
)


class SopLock:
    name = "sop-lock"
    needs: frozenset[str] = frozenset()

    def applies(self, ctx: CheckContext) -> str | None:
        return None if is_workshop_root(ctx.root) else HIDDEN

    def run(self, ctx: CheckContext) -> Step:
        from forge.sop_lock import run_sop_lock

        buf_out = io.StringIO()
        buf_err = io.StringIO()
        code = run_sop_lock(ctx.root, stdout=buf_out, stderr=buf_err)
        print_captured(buf_err.getvalue(), ctx.err)
        if code != EXIT_OK:
            return Step(self.name, "fail", last_line(buf_err.getvalue()) or f"exit {code}")
        return Step(self.name, "ok", last_line(buf_out.getvalue()))
