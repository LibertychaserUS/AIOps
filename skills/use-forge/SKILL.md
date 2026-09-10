---
name: use-forge
description: >-
  SOP for installing and using Forge on a GitHub repo. PR-only protected
  branches, no direct push, no self-merge. Use when adopting Forge, running
  forge apply/status, writing agent policy, or asking how people and agents
  land code. Do not use for Overlay inbox/suites (use use-overlay).
---

# Use Forge

Forge is a standard part: Ruleset + policy + optional guard. It does not generate tests and must not edit Overlay `status`.

## Instructions

1. **Read the adopter repo first.** Copy `forge.yaml` from `forge/forge.example.yaml`. Set `protect`, `agent_branch_prefixes`, `deny_paths` (the existing build workflow, never invent a product Verify name unless the adopter already has one).
2. **Paste policy**, do not invent a second constitution. Copy [`forge/agent-policy.md`](../../forge/agent-policy.md) into the adopter `AGENTS.md`.
3. **Dry-run before write.**
   ```text
   python -m forge apply --repo OWNER/NAME --path forge.yaml --dry-run
   ```
   Must print the payload and `copy these files`. Exit 0. No API write.
4. **Apply only with an admin token** (`FORGE_GITHUB_TOKEN` or `GITHUB_TOKEN`, Administration: write). Never apply to `First-Light-TechHK/LearningGuidePortal` from this workshop. Never apply in Overlay CI.
   ```text
   python -m forge apply --repo OWNER/NAME --path forge.yaml
   python -m forge status --repo OWNER/NAME
   ```
5. **Humans and agents land the same way:** open a PR. No push to protected branches. No self-merge. No self-approve. Do not edit the adopter’s existing build workflow.
6. **Do not touch Overlay gates.** Forge must not write `reviewed_by`, receipts, or `status: armed`.
7. **Required checks** stay the adopter’s names (their build job, plus `overlay-check` only if they installed Overlay). Forge does not create those jobs.

Guard workflow is later. First slice is Ruleset + policy + CLI.

## Examples

```text
# This workshop
python -m forge apply --repo LibertychaserUS/AIOps --path forge.yaml --dry-run
```

Illegal: `apply --repo First-Light-TechHK/LearningGuidePortal`. Illegal: apply on `on: push` Overlay jobs.

## Performance Notes

Dry-run is local JSON. Live apply is one GET + one POST or PUT. No model. No CD.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 退出码 2 | 缺 token。不要部分写入。 |
| 退出码 3 | `forge.yaml` 非法。对照 example。 |
| 退出码 4 | GitHub API 失败。看权限，不要改 Ruleset JSON 结构凑合。 |
| 想直推 main 省事 | 停。开 PR。 |
| 想让 Forge 把 suite 标 armed | 停。那是人审 Overlay。 |
