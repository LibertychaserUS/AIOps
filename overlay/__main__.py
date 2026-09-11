"""python -m overlay validate|select|review|run|cover|migrate"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from overlay import EXIT_CONTRACT, EXIT_OK
from overlay.cover import run_cover
from overlay.migrate import run_migrate
from overlay.review import run_review
from overlay.run import DEFAULT_TIMEOUT, run_run
from overlay.select import default_select_branch, run_select
from overlay.validate import run_validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m overlay",
        description=(
            "Overlay: validate inbox/suites, select active suites, run their "
            "product_command, report cover, migrate v1 suites. No generate. "
            "No model on this path."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    validate_p = sub.add_parser("validate", help="validate inbox + suites + overlay.yaml")
    validate_p.add_argument("--root", default=".", help="adopter overlay root (default: .)")

    select_p = sub.add_parser("select", help="print active suite ids for a branch")
    select_p.add_argument(
        "--branch",
        default=None,
        help="branch name from overlay.yaml (default: GITHUB_BASE_REF, then GITHUB_REF_NAME, then main)",
    )
    select_p.add_argument("--root", default=".", help="adopter overlay root (default: .)")
    select_p.add_argument(
        "--write-receipt",
        metavar="DIR",
        default=None,
        help="directory for a program-written receipt (wrote_by=select)",
    )

    review_p = sub.add_parser("review", help="human review (refuses without --i-am; no writes yet)")
    review_p.add_argument("--suite", default=None)
    review_p.add_argument("--status", choices=("blocked", "active"), default=None)
    review_p.add_argument("--i-am", dest="i_am", default=None, help="human identity; required")
    review_p.add_argument("--reason", default=None)

    run_p = sub.add_parser("run", help="select active suites and run product_command")
    run_p.add_argument(
        "--branch",
        default=None,
        help="branch name from overlay.yaml (default: GITHUB_BASE_REF, then GITHUB_REF_NAME, then main)",
    )
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

    cover_p = sub.add_parser("cover", help="print function_id triad + invariant coverage")
    cover_p.add_argument("--root", default=".", help="adopter overlay root (default: .)")

    migrate_p = sub.add_parser("migrate", help="rewrite suite.yaml draft/armed to overlay-suite/v2")
    migrate_p.add_argument("--root", default=".", help="adopter overlay root (default: .)")
    migrate_p.add_argument(
        "--dry-run",
        action="store_true",
        help="print rewrites without writing files",
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
        branch = (args.branch or "").strip() or default_select_branch()
        return run_select(
            Path(args.root),
            branch,
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
        branch = (args.branch or "").strip() or default_select_branch()
        return run_run(
            Path(args.root),
            branch,
            write_receipt_dir=Path(args.write_receipt),
            workdir=Path(args.workdir),
            timeout=timeout,
            stdout=out,
            stderr=err,
        )
    if args.command == "cover":
        return run_cover(Path(args.root), stdout=out, stderr=err)
    if args.command == "migrate":
        return run_migrate(
            Path(args.root),
            dry_run=bool(args.dry_run),
            stdout=out,
            stderr=err,
        )
    parser.print_help(err)
    return EXIT_CONTRACT


if __name__ == "__main__":
    raise SystemExit(main())
