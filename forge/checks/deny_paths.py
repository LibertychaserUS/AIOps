"""deny_paths row: the local diff must not touch forge.yaml deny_paths."""

from __future__ import annotations

from forge.checks.base import NEED_BASE, NEED_FORGE_YAML, NEED_GIT, CheckContext, Step
from forge.gitutil import matching_agent_prefix, no_base_detail
from forge.pathmatch import path_is_denied


class DenyPaths:
    """Fail when the local diff touches forge.yaml deny_paths. No GitHub write.

    agent_branch_prefixes are recorded (design 3.5.2: human branches stay allowed).
    They are not a local fail in this cut. No visible base fails closed.
    """

    name = "deny_paths"
    needs = frozenset({NEED_FORGE_YAML, NEED_GIT, NEED_BASE})

    def applies(self, ctx: CheckContext) -> str | None:
        return None

    def run(self, ctx: CheckContext) -> Step:
        config = ctx.config
        assert config is not None
        if ctx.changed is None:
            return Step(self.name, "skip", "no git work tree")
        hits = [path for path in ctx.changed if path_is_denied(path, config.deny_paths)]
        prefix = matching_agent_prefix(ctx.branch, config.agent_branch_prefixes)
        suffix = f"; agent branch {ctx.branch}" if prefix and ctx.branch else ""
        if hits:
            shown = ", ".join(hits)
            return Step(self.name, "fail", f"diff touches {shown}{suffix}")
        if not ctx.base_ref:
            return Step(self.name, "fail", no_base_detail(config.protect))
        return Step(self.name, "ok", f"vs {ctx.base_ref}{suffix}")
