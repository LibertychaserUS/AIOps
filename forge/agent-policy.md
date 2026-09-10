# Forge agent policy (paste into the consuming repo AGENTS.md)

Review and merge are GitHub humans + repository Ruleset. Forge does not merge. Overlay does not merge. CodeRabbit is advisory and is never the only merge gate.

- Open a pull request. Title: `[<role>][<product>] <imperative>` (role: 管理|开发|agent; product: Forge|Overlay|CI|docs). Body headings: `docs/pr-brief.md`. Do not invent branch, workflow, or skill prefixes; leave `cursor/` / `copilot/` alone. Do not push protected branches (`main` unless the repo lists others).
- Do not merge your own PR. Do not approve your own PR.
- Do not live `forge apply`. Do not edit Rulesets or required checks.
- Do not edit the consuming repo's existing build workflow (the Verify equivalent).
- Do not write Overlay `reviewed_by`, receipts, or change `status` to `armed`.
- Do not call production URLs. Do not deploy.
- You may `workflow_dispatch` Overlay `generate` when a human asked.
