"""overlay validate / overlay cover rows: run when the root has overlay.yaml."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TextIO

from forge import EXIT_OK
from forge.checks.base import (
    EXIT_CHECK,
    CheckContext,
    OverlayFn,
    Step,
    last_line,
    overlay_yaml_exists,
    print_captured,
)


def default_overlay_validate(root: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        from overlay.validate import run_validate
    except ImportError as exc:
        print(f"overlay validate: cannot import overlay ({exc})", file=stderr)
        return EXIT_CHECK
    return run_validate(root, stdout=stdout, stderr=stderr)


def default_overlay_cover(root: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        from overlay.cover import run_cover
    except ImportError as exc:
        print(f"overlay cover: cannot import overlay ({exc})", file=stderr)
        return EXIT_CHECK
    return run_cover(root, stdout=stdout, stderr=stderr)


def _run_overlay(name: str, fn: OverlayFn, ctx: CheckContext) -> Step:
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    code = fn(ctx.root, buf_out, buf_err)
    print_captured(buf_err.getvalue(), ctx.err)
    if code != EXIT_OK:
        return Step(name, "fail", f"exit {code}")
    return Step(name, "ok", last_line(buf_out.getvalue()))


class OverlayValidate:
    name = "overlay validate"
    needs: frozenset[str] = frozenset()

    def applies(self, ctx: CheckContext) -> str | None:
        return None if overlay_yaml_exists(ctx.root) else "no overlay.yaml"

    def run(self, ctx: CheckContext) -> Step:
        fn = default_overlay_validate if ctx.overlay_validate is None else ctx.overlay_validate
        return _run_overlay(self.name, fn, ctx)


class OverlayCover:
    name = "overlay cover"
    needs: frozenset[str] = frozenset()

    def applies(self, ctx: CheckContext) -> str | None:
        return None if overlay_yaml_exists(ctx.root) else "no overlay.yaml"

    def run(self, ctx: CheckContext) -> Step:
        fn = default_overlay_cover if ctx.overlay_cover is None else ctx.overlay_cover
        return _run_overlay(self.name, fn, ctx)
