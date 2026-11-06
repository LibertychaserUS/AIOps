"""unittest row: the workshop's own `unittest discover`, same command as CI."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from forge import EXIT_OK
from forge.checks.base import (
    EXIT_CHECK,
    HIDDEN,
    CheckContext,
    Step,
    is_workshop_root,
    print_captured,
)

CHECK_ENV = "FORGE_CHECK_RUNNING"

# Same command as the CI job `unittest`. Adopter roots never reach this.
WORKSHOP_UNITTEST_ARGS = ("discover", "-s", "tests", "-t", ".", "-q")


def workshop_unittest_args(root: Path) -> tuple[str, ...] | None:
    """Full discover, matching CI. None when this root has no workshop tests/."""
    if not (root / "tests").is_dir():
        return None
    return WORKSHOP_UNITTEST_ARGS


def default_unittest_runner(
    root: Path,
    modules: Sequence[str],
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    env = os.environ.copy()
    env[CHECK_ENV] = "1"
    pythonpath = str(root)
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath = pythonpath + os.pathsep + existing
    env["PYTHONPATH"] = pythonpath
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", *modules],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    print_captured(proc.stdout, stdout)
    if proc.returncode != 0:
        print_captured(proc.stderr or "unittest failed", stderr)
        return EXIT_CHECK
    return EXIT_OK


class Unittest:
    name = "unittest"
    needs: frozenset[str] = frozenset()

    def applies(self, ctx: CheckContext) -> str | None:
        if not is_workshop_root(ctx.root):
            return HIDDEN
        nested = bool(ctx.env.get(CHECK_ENV)) or bool(os.environ.get(CHECK_ENV))
        if not ctx.run_unittests:
            return "disabled"
        if nested:
            return "already inside forge check"
        if not workshop_unittest_args(ctx.root):
            return "no workshop tests/"
        return None

    def run(self, ctx: CheckContext) -> Step:
        modules = workshop_unittest_args(ctx.root)
        assert modules is not None
        fn = default_unittest_runner if ctx.unittest_runner is None else ctx.unittest_runner
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        code = fn(ctx.root, modules, buf_out, buf_err)
        print_captured(buf_err.getvalue(), ctx.err)
        if code != EXIT_OK:
            return Step(self.name, "fail", f"exit {code}")
        return Step(self.name, "ok", " ".join(modules))
