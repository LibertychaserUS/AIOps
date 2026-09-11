# Forge agent policy (paste into the consuming repo AGENTS.md)

Review and merge are GitHub humans + repository Ruleset. Forge does not merge. Overlay does not merge. CodeRabbit is advisory and is never the only merge gate.

- Open a draft PR with `python -m forge submit` onto `protect[0]` (usually `dev`) only after `python -m forge check` is green **and** `FORGE_SUBMIT_TOKEN` is set (PAT / fine-grained / GitHub App token). `submit` runs the same check first; red check or missing `FORGE_SUBMIT_TOKEN` means no push and no PR, including `--dry-run`. Ambient `gh auth`, `GH_TOKEN`, git extraheader, and CI `GITHUB_TOKEN` are not enough. Do not paste a PAT into chat. Never print the token. Ops merge uses other permissions, not this submit secret. Title must pass `python -m forge pr-title` (`title.scopes: any` = Conventional Commits syntax; a list keeps `type(product/actor): subject`). Body headings: `docs/pr-brief.md`. Promote `dev` → `main` with `python -m forge promote`; the command never merges. The PR onto a protected branch is the **squash 封顶**: one slice, then reopen from the new base SHA. Do not invent branch, workflow, or skill prefixes. Do not push protected branches. When those jobs exist, do not land a PR that is red on `overlay-check`, `pr-title`, `forge-check`, `sop-lock`, or `unittest`.
- Do not merge your own PR. Do not approve your own PR. Forge does not merge.
- Write the PR body from the diff: every item under 做了什么 must map to a change in `git diff --stat`, and every workflow / suite `status` / `forge.yaml` / `overlay.yaml` / migration change must appear in the body. A reviewing agent checks body ↔ diff line by line and also checks that the PR carried its context (`docs/STATE.md`, ADR, `CHANGELOG.md`, `docs_sync` targets); mismatches are request-changes, never approve.
- Do not live `forge apply`. Do not edit Rulesets or required checks.
- Do not edit the consuming repo's existing build workflow.
- Do not change Overlay suite `status` to `blocked` on an agent branch (`suite_guard` fails). Humans review suites.
- Do not call production URLs. Do not deploy.
- You may `workflow_dispatch` Overlay `generate` when a human asked.
