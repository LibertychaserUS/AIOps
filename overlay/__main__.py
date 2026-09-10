"""python -m overlay validate|select|review|run"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from overlay import EXIT_CONTRACT, EXIT_OK
from overlay.review import run_review
from overlay.run import DEFAULT_TIMEOUT, run_run
from overlay.select import run_select
from overlay.validate import run_validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m overlay",
        description=(
            "Overlay: validate inbox/suites, select armed suites, run their "
            "product_command. No generate. No model on this path."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    validate_p = sub.add_parser("validate", help="validate inbox + suites + overlay.yaml")
    validate_p.add_argument("--root", default=".", help="adopter overlay root (default: .)")

    select_p = sub.add_parser("select", help="print armed suite ids for a branch")
    select_p.add_argument("--branch", required=True, help="branch name from overlay.yaml")
    select_p.add_argument("--root", default=".", help="adopter overlay root (default: .)")
    select_p.add_argument(
        "--write-receipt",
        metavar="DIR",
        default=None,
        help="directory for a program-written receipt (wrote_by=select)",
    )

    review_p = sub.add_parser("review", help="human review (refuses without --i-am; no writes yet)")
    review_p.add_argument("--suite", default=None)
    review_p.add_argument("--status", choices=("blocked", "armed"), default=None)
    review_p.add_argument("--i-am", dest="i_am", default=None, help="human identity; required")
    review_p.add_argument("--reason", default=None)

    run_p = sub.add_parser("run", help="select armed suites and run product_command")
    run_p.add_argument("--branch", required=True, help="branch name from overlay.yaml")
    run_p.add_argument("--root", default=".", help="adopter overlay root (default: .)")
    run_p.add_argument(
        "--write-receipt",
        metavar="DIR",
        required=True,
        help="directory for a program-written receipt (wrote_by=run); required",
    )
    run_p.add_argument(
        "--workdir",
        default=".",
        help="directory to run product_command in (caller checkout; no foreign clone)",
    )
    run_p.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"seconds per command (default {DEFAULT_TIMEOUT})",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        code = exc.code
        if code in (0, None):
            return EXIT_OK
        return EXIT_CONTRACT

    if not args.command:
        parser.print_help(err)
        return EXIT_CONTRACT
    if args.command == "validate":
        return run_validate(Path(args.root), stdout=out, stderr=err)
    if args.command == "select":
        receipt_dir = Path(args.write_receipt) if args.write_receipt else None
        return run_select(
            Path(args.root),
            args.branch,
            write_receipt_dir=receipt_dir,
            stdout=out,
            stderr=err,
        )
    if args.command == "review":
        return run_review(
            i_am=args.i_am,
            suite=args.suite,
            status=args.status,
            reason=args.reason,
            stderr=err,
        )
    if args.command == "run":
        timeout = args.timeout if args.timeout and args.timeout > 0 else DEFAULT_TIMEOUT
        return run_run(
            Path(args.root),
            args.branch,
            write_receipt_dir=Path(args.write_receipt),
            workdir=Path(args.workdir),
            timeout=timeout,
            stdout=out,
            stderr=err,
        )
    parser.print_help(err)
    return EXIT_CONTRACT


if __name__ == "__main__":
    raise SystemExit(main())
