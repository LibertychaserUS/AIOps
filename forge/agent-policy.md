# Forge agent policy (paste into the consuming repo AGENTS.md)

Review and merge are GitHub humans + repository Ruleset. Forge does not merge. Overlay does not merge. CodeRabbit is advisory and is never the only merge gate.

- Open a draft PR with `python -m forge submit` (开发侧代推) only after `python -m forge check` is green **and** `FORGE_SUBMIT_TOKEN` is set (PAT / fine-grained / GitHub App token). `submit` runs the same check first; red check or missing `FORGE_SUBMIT_TOKEN` means no push and no PR, including `--dry-run`. Ambient `gh auth`, `GH_TOKEN`, git extraheader, and CI `GITHUB_TOKEN` are not enough. Do not paste a PAT into chat. Never print the token. Ops merge uses other permissions, not this submit secret. Title must pass `python -m forge pr-title` (Conventional Commits `type(product/actor): subject`; actor `dev|admin|agent`). Body headings: `docs/pr-brief.md`. Do not invent branch, workflow, or skill prefixes; leave `cursor/` / `copilot/` alone. Do not push protected branches (`main` unless the repo lists others). Do not merge, approve, or arm. When those jobs exist, do not land a PR that is red on `overlay-check`, `pr-title`, `forge-check`, or `sop-lock`.
- Do not merge your own PR. Do not approve your own PR. Forge does not merge.
- Do not live `forge apply`. Do not edit Rulesets or required checks.
- Do not edit the consuming repo's existing build workflow (the Verify equivalent).
- Do not write Overlay `reviewed_by`, receipts, or change `status` to `armed`.
- Do not call production URLs. Do not deploy.
- You may `workflow_dispatch` Overlay `generate` when a human asked.
