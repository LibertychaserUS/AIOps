"""python -m forge apply|status|submit|promote|check|pr-title|sop-lock|ci-select|ops-review|bounce|release"""

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
from forge.check import run_check
from forge.status import run_status
from forge.submit import run_submit
from forge.title import resolve_arg_or_env, run_pr_title


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m forge",
        description=(
            "Forge: 开发侧 check + submit (代推 draft PR); Ops apply/status (Ruleset); "
            "Ops release (product tags). Does not merge. Does not write CODEOWNERS, AGENTS.md, or workflows."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    apply_p = sub.add_parser("apply", help="create or update forge-protected-<branch> and forge-protected-tags")
    apply_p.add_argument("--repo", required=True, help="OWNER/NAME")
    apply_p.add_argument("--path", default=None, help="forge.yaml (optional; defaults protect=main)")
    apply_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="print all ruleset payloads and exit 0 without writing",
    )

    status_p = sub.add_parser("status", help="read-only: installed / missing / drifted per ruleset")
    status_p.add_argument("--repo", required=True, help="OWNER/NAME")
    status_p.add_argument("--root", default=".", help="repo root (default: .)")
    status_p.add_argument("--path", default=None, help="forge.yaml (optional)")
    status_p.add_argument(
        "--write",
        default=None,
        help="write a generated Chinese status page (e.g. docs/STATE.md)",
    )
    status_p.add_argument(
        "--check-state",
        action="store_true",
        dest="check_state",
        help="fail if docs/STATE.md is missing or stale vs forge.yaml + git",
    )

    check_p = sub.add_parser(
        "check",
        help="local pre-submit gate. Exit 0/2. No GitHub write. submit refuses if this is red.",
    )
    check_p.add_argument("--root", default=".", help="repo root (default: .)")
    check_p.add_argument(
        "--title",
        default=None,
        help="PR title to lint (same as pr-title). Default: env PR_TITLE. Skip if omitted or blank.",
    )
    check_p.add_argument(
        "--body",
        default=None,
        help="PR body to lint when docs/pr-brief.md exists. Default: env PR_BODY. Skip if omitted or blank.",
    )

    submit_p = sub.add_parser(
        "submit",
        help="开发侧代推: run forge check, then push the feature branch and open/update a draft PR. Never merges.",
    )
    submit_p.add_argument("--repo", required=True, help="OWNER/NAME")
    submit_p.add_argument(
        "--title",
        default=None,
        help="PR title. Must pass python -m forge pr-title.",
    )
    submit_p.add_argument("--path", default=None, help="forge.yaml (optional; defaults protect=main)")
    submit_p.add_argument(
        "--head",
        default=None,
        help="Feature branch to submit. Default: current HEAD, else GITHUB_HEAD_REF.",
    )
    submit_p.add_argument(
        "--base",
        default=None,
        help="PR base. Default: protect[0]. Must be a protect branch.",
    )
    submit_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help=(
            "print intended remote branch + PR title/body headings; no push. "
            "Still requires FORGE_SUBMIT_TOKEN (fail-closed if missing). Red if check is red."
        ),
    )

    title_p = sub.add_parser(
        "pr-title",
        aliases=["title"],
        help="lint a GitHub PR title (Conventional Commits + product/actor). Exit 0/2. No GitHub write.",
    )
    title_p.add_argument(
        "--title",
        default=None,
        help='PR title, e.g. "feat(overlay/dev): add cover triad". Default: env PR_TITLE. Skip if omitted or blank.',
    )
    title_p.add_argument(
        "--body",
        default=None,
        help="PR body. Default: env PR_BODY. Skip if omitted or blank. Lint six 解说规格 headings when docs/pr-brief.md exists.",
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

    select_p = sub.add_parser(
        "ci-select",
        help="decide whether a CI check runs (common always; product via forge.yaml). Exit 0/3.",
    )
    select_p.add_argument("--root", default=".", help="repo root (default: .)")
    select_p.add_argument(
        "--check",
        required=True,
        help="check name: pr-title, sop-lock, overlay-check, or forge-check",
    )
    select_p.add_argument(
        "--title",
        default=None,
        help="PR title. Default: env PR_TITLE. Title product facet wins when valid.",
    )
    select_p.add_argument(
        "--changed",
        nargs="*",
        default=None,
        help="Changed paths when no valid title (push). Omit to use git HEAD~1.",
    )
    select_p.add_argument(
        "--github-output",
        action="store_true",
        dest="github_output",
        help="append run=true|false to $GITHUB_OUTPUT (skip is success)",
    )

    review_p = sub.add_parser(
        "ops-review",
        help="Overlay Ops: observe CodeRabbit/Copilot comments (advisory). Never a merge gate.",
    )
    review_p.add_argument("--repo", required=True, help="OWNER/NAME")
    review_p.add_argument("--sha", default="", help="head SHA for check-runs")
    review_p.add_argument("--pr", type=int, default=0, help="pull number")
    review_p.add_argument("--write-report", required=True, help="directory for review-bots.yaml")
    review_p.add_argument("--wait", type=int, default=0, dest="wait_s", help="seconds to poll")
    review_p.add_argument("--poll", type=int, default=5, dest="poll_s")

    promote_p = sub.add_parser(
        "promote",
        help="open or update a promote PR (from → to). Never merges. Needs FORGE_SUBMIT_TOKEN.",
    )
    promote_p.add_argument("--repo", required=True, help="OWNER/NAME")
    promote_p.add_argument("--from", dest="from_branch", required=True, help="source branch (e.g. dev)")
    promote_p.add_argument("--to", dest="to_branch", required=True, help="target branch (e.g. main)")
    promote_p.add_argument("--path", default=None, help="forge.yaml (optional)")
    promote_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="print the intended PR; no GitHub write. Still requires FORGE_SUBMIT_TOKEN.",
    )

    bounce_p = sub.add_parser(
        "bounce",
        help="Overlay Ops: 打回 PR + write ops-debug.yaml. Never merges.",
    )
    bounce_p.add_argument("--repo", required=True, help="OWNER/NAME")
    bounce_p.add_argument("--pr", type=int, required=True)
    bounce_p.add_argument("--failed", default="", help="comma-separated failed job names")
    bounce_p.add_argument("--write-report", required=True, help="directory for ops-debug.yaml")
    bounce_p.add_argument("--run-url", default="", dest="run_url")
    bounce_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="write the report only; no PR comment",
    )

    release_p = sub.add_parser(
        "release",
        help="Ops: publish overlay-v* and/or forge-v* GitHub Releases. Not production CD. Never merges.",
    )
    release_p.add_argument("--repo", required=True, help="OWNER/NAME")
    release_p.add_argument("--version", required=True, help="semver without prefix, e.g. 1.0.1")
    release_p.add_argument(
        "--products",
        default="both",
        help="both (default), overlay, or forge",
    )
    release_p.add_argument(
        "--sha",
        default=None,
        help="commit to tag. Default: origin/main via API (or GITHUB_SHA).",
    )
    release_p.add_argument("--root", default=".", help="workshop root for __version__ check")
    release_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="print the two release payloads; no GitHub write. No token required.",
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
    check_fn: Any | None = None,
    credential_probe: Any | None = None,
    pusher: Any | None = None,
    pr_create: Any | None = None,
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
            root=Path(args.root),
            path=args.path,
            write=args.write,
            check_state=args.check_state,
        )
    if args.command == "check":
        title = resolve_arg_or_env(args.title, env_dict, "PR_TITLE")
        body = resolve_arg_or_env(args.body, env_dict, "PR_BODY")
        return run_check(
            Path(args.root),
            title=title,
            body=body,
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
            head=args.head,
            base=args.base,
            urlopen=opener,
            base_url=api,
            stdout=out,
            stderr=err,
            environ=env_dict,
            check_fn=check_fn,
            pusher=pusher,
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
        title = resolve_arg_or_env(title, env_dict, "PR_TITLE")
        body = resolve_arg_or_env(body, env_dict, "PR_BODY")
        code = run_pr_title(
            title=title,
            environ=env_dict,
            stdout=out,
            stderr=err,
            root=Path(args.root),
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
        from forge.sop_lock import run_sop_lock

        return run_sop_lock(Path(args.root), stdout=out, stderr=err)
    if args.command == "ci-select":
        from forge.ci_select import run_ci_select

        title = resolve_arg_or_env(args.title, env_dict, "PR_TITLE")
        return run_ci_select(
            Path(args.root),
            check=args.check,
            title=title,
            changed=args.changed,
            github_output=args.github_output,
            stdout=out,
            stderr=err,
            environ=env_dict,
        )
    if args.command == "promote":
        from forge.promote import run_promote

        return run_promote(
            repo=args.repo,
            from_branch=args.from_branch,
            to_branch=args.to_branch,
            path=args.path,
            dry_run=args.dry_run,
            urlopen=opener,
            base_url=api,
            stdout=out,
            stderr=err,
            environ=env_dict,
        )
    if args.command == "ops-review":
        from forge.ops_chain import run_review_bots

        return run_review_bots(
            repo=args.repo,
            sha=args.sha,
            pr=args.pr,
            write_report=Path(args.write_report),
            urlopen=opener,
            base_url=api,
            environ=env_dict,
            stdout=out,
            stderr=err,
            wait_s=args.wait_s,
            poll_s=args.poll_s,
        )
    if args.command == "release":
        from forge.release import run_release

        sha = args.sha if args.sha is not None else env_dict.get("GITHUB_SHA")
        return run_release(
            repo=args.repo,
            version=args.version,
            products=args.products,
            sha=sha,
            root=Path(args.root),
            dry_run=args.dry_run,
            urlopen=opener,
            base_url=api,
            stdout=out,
            stderr=err,
            environ=env_dict,
        )
    if args.command == "bounce":
        from forge.ops_chain import run_bounce

        failed = [part.strip() for part in str(args.failed).split(",") if part.strip()]
        return run_bounce(
            repo=args.repo,
            pr=args.pr,
            failed=failed,
            write_report=Path(args.write_report),
            urlopen=opener,
            base_url=api,
            environ=env_dict,
            stdout=out,
            stderr=err,
            run_url=args.run_url,
            dry_run=args.dry_run,
        )
    parser.print_help(err)
    return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
