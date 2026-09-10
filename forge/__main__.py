"""python -m forge apply|status|pr-title"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Any, TextIO

from forge import EXIT_CONFIG, EXIT_OK
from forge.apply import DEFAULT_API, default_urlopen, run_apply
from forge.status import run_status
from forge.title import run_pr_title


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m forge",
        description="Install or inspect the Forge GitHub ruleset. Lint PR titles. Does not write CODEOWNERS, AGENTS.md, or workflows.",
    )
    sub = parser.add_subparsers(dest="command")

    apply_p = sub.add_parser("apply", help="create or update forge-protected-default")
    apply_p.add_argument("--repo", required=True, help="OWNER/NAME")
    apply_p.add_argument("--path", default=None, help="forge.yaml (optional; defaults protect=main)")
    apply_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="print the ruleset payload and exit 0 without writing",
    )

    status_p = sub.add_parser("status", help="read-only: is the ruleset installed?")
    status_p.add_argument("--repo", required=True, help="OWNER/NAME")

    title_p = sub.add_parser(
        "pr-title",
        aliases=["title"],
        help="lint a GitHub PR title (Conventional Commits + product/actor). Exit 0/2. No GitHub write.",
    )
    title_p.add_argument(
        "--title",
        default=None,
        help='PR title, e.g. "feat(overlay/dev): add cover triad". Default: env PR_TITLE.',
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    urlopen: Any | None = None,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    base_url: str | None = None,
) -> int:
    env: Mapping[str, str] = os.environ if environ is None else environ
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser = _parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        code = exc.code
        return EXIT_CONFIG if code not in (EXIT_OK, None) else EXIT_OK

    if not args.command:
        parser.print_help(err)
        return EXIT_CONFIG

    opener = urlopen or default_urlopen
    api = base_url or str(env.get("FORGE_GITHUB_API") or DEFAULT_API)
    env_dict = dict(env)

    if args.command == "apply":
        return run_apply(
            repo=args.repo,
            path=args.path,
            dry_run=args.dry_run,
            urlopen=opener,
            base_url=api,
            stdout=out,
            stderr=err,
            environ=env_dict,
        )
    if args.command == "status":
        return run_status(
            repo=args.repo,
            urlopen=opener,
            base_url=api,
            stdout=out,
            stderr=err,
            environ=env_dict,
        )
    if args.command in {"pr-title", "title"}:
        return run_pr_title(
            title=args.title,
            environ=env_dict,
            stdout=out,
            stderr=err,
        )
    parser.print_help(err)
    return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
