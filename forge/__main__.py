"""python -m forge apply|status|submit|pr-title|sop-lock"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from forge import EXIT_CONFIG, EXIT_OK
from forge.apply import DEFAULT_API, default_urlopen, run_apply
from forge.brief import brief_spec_exists, lint_pr_body
from forge.sop_lock import run_sop_lock
from forge.status import run_status
from forge.submit import run_submit
from forge.title import run_pr_title


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m forge",
        description=(
            "Forge: 开发侧 submit (代推 draft PR); Ops apply/status (Ruleset); pr-title lint. "
            "Does not merge. Does not write CODEOWNERS, AGENTS.md, or workflows."
        ),
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

    submit_p = sub.add_parser(
        "submit",
        help="开发侧代推: push the feature branch and open/update a draft PR. Never merges.",
    )
    submit_p.add_argument("--repo", required=True, help="OWNER/NAME")
    submit_p.add_argument(
        "--title",
        default=None,
        help="PR title. Must pass python -m forge pr-title.",
    )
    submit_p.add_argument("--path", default=None, help="forge.yaml (optional; defaults protect=main)")
    submit_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="print intended remote branch + PR title/body headings; no push; exit 0",
    )

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
    title_p.add_argument(
        "--body",
        default=None,
        help="PR body. Default: env PR_BODY. Lint six 解说规格 headings when docs/pr-brief.md exists.",
    )
    title_p.add_argument(
        "--event",
        default=None,
        help="GitHub event JSON path (reads pull_request.title / pull_request.body).",
    )
    title_p.add_argument(
        "--root",
        default=".",
        help="Repo root used to detect docs/pr-brief.md (default: .).",
    )

    sop_p = sub.add_parser(
        "sop-lock",
        help="decidable SOP locks (workflows, kernel, skills Lock, required_checks). Exit 0/2.",
    )
    sop_p.add_argument("--root", default=".", help="repo root (default: .)")
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
    if args.command == "submit":
        return run_submit(
            repo=args.repo,
            title=args.title,
            dry_run=args.dry_run,
            path=args.path,
            urlopen=opener,
            base_url=api,
            stdout=out,
            stderr=err,
            environ=env_dict,
        )
    if args.command in {"pr-title", "title"}:
        title = args.title
        body = args.body
        if args.event:
            try:
                payload = json.loads(Path(args.event).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"cannot read --event: {exc}", file=err)
                return EXIT_CONFIG
            pull = payload.get("pull_request") if isinstance(payload, dict) else None
            if not isinstance(pull, dict):
                print("--event JSON has no pull_request", file=err)
                return EXIT_CONFIG
            if title is None:
                raw_title = pull.get("title")
                title = raw_title if isinstance(raw_title, str) else None
            if body is None:
                raw_body = pull.get("body")
                body = raw_body if isinstance(raw_body, str) else None
        if title is None:
            title = env_dict.get("PR_TITLE")
        if body is None:
            body = env_dict.get("PR_BODY")
        code = run_pr_title(
            title=title,
            environ=env_dict,
            stdout=out,
            stderr=err,
        )
        if code != EXIT_OK:
            return code
        if body is not None and brief_spec_exists(Path(args.root)):
            brief_code, message = lint_pr_body(body)
            if brief_code != EXIT_OK:
                print(message, file=err)
                return brief_code
        return EXIT_OK
    if args.command == "sop-lock":
        return run_sop_lock(Path(args.root), stdout=out, stderr=err)
    parser.print_help(err)
    return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
