"""pr-title / pr-body rows: the PR spec, source resolved per event by the runner."""

from __future__ import annotations

import io

from forge import EXIT_OK
from forge.brief import brief_spec_exists, lint_pr_body
from forge.checks.base import CheckContext, Step, print_captured
from forge.title import run_pr_title


class PrTitle:
    name = "pr-title"
    needs: frozenset[str] = frozenset()

    def applies(self, ctx: CheckContext) -> str | None:
        if ctx.title_ref.text is None:
            return "no spec; pull_request lints PR_TITLE, push lints commit"
        return None

    def run(self, ctx: CheckContext) -> Step:
        title = ctx.title_ref.text
        assert title is not None
        buf_err = io.StringIO()
        code = run_pr_title(
            title=title,
            environ=ctx.env,
            stdout=ctx.out,
            stderr=buf_err,
            root=ctx.root,
        )
        print_captured(buf_err.getvalue(), ctx.err)
        if code != EXIT_OK:
            return Step(self.name, "fail", buf_err.getvalue().strip() or f"exit {code}")
        return Step(self.name, "ok", f"{ctx.title_ref.source}: {title}")


class PrBody:
    name = "pr-body"
    needs: frozenset[str] = frozenset()

    def applies(self, ctx: CheckContext) -> str | None:
        if not brief_spec_exists(ctx.root):
            return "no docs/pr-brief.md"
        if ctx.body_ref.text is None:
            return "no spec; pull_request lints PR_BODY"
        return None

    def run(self, ctx: CheckContext) -> Step:
        code, message = lint_pr_body(ctx.body_ref.text)
        if code != EXIT_OK:
            return Step(self.name, "fail", message or f"exit {code}")
        return Step(self.name, "ok", "six ## headings")
