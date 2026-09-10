"""Human review CLI. Slice 1 refuses writes; --i-am is required."""

from __future__ import annotations

import sys
from typing import TextIO

from overlay import EXIT_CONTRACT


def run_review(
    *,
    i_am: str | None,
    suite: str | None = None,
    status: str | None = None,
    reason: str | None = None,
    stderr: TextIO | None = None,
) -> int:
    err = sys.stderr if stderr is None else stderr
    if not (i_am or "").strip():
        print("overlay review refuses without --i-am HUMAN", file=err)
        return EXIT_CONTRACT
    print(
        "overlay review: --i-am is recorded as human, but writes are not in this slice",
        file=err,
    )
    return EXIT_CONTRACT
