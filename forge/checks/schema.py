"""schema/check.py row: workshop root with schema/check.py only."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path
from typing import TextIO

from forge import EXIT_OK
from forge.checks.base import (
    EXIT_CHECK,
    HIDDEN,
    CheckContext,
    Step,
    is_workshop_root,
    last_line,
    print_captured,
    schema_check_exists,
)


def default_schema_runner(root: Path, stdout: TextIO, stderr: TextIO) -> int:
    script = root / "schema" / "check.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    print_captured(proc.stdout, stdout)
    if proc.returncode != 0:
        print_captured(proc.stderr or "schema/check.py failed", stderr)
        return EXIT_CHECK
    return EXIT_OK


class SchemaCheck:
    name = "schema/check.py"
    needs: frozenset[str] = frozenset()

    def applies(self, ctx: CheckContext) -> str | None:
        if is_workshop_root(ctx.root) and schema_check_exists(ctx.root):
            return None
        return HIDDEN

    def run(self, ctx: CheckContext) -> Step:
        fn = default_schema_runner if ctx.schema_runner is None else ctx.schema_runner
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        code = fn(ctx.root, buf_out, buf_err)
        print_captured(buf_err.getvalue(), ctx.err)
        if code != EXIT_OK:
            return Step(self.name, "fail", f"exit {code}")
        return Step(self.name, "ok", last_line(buf_out.getvalue()))
