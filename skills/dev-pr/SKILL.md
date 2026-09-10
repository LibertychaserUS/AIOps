---
name: dev-pr
description: Act as 开发端 (human developer) on a Forge-protected GitHub repo. This skill should be used when opening a PR, requesting review, or fixing an armed Overlay failure. Do not use to apply Rulesets, merge-gate setup, live forge apply, or write reviewed_by / armed (use manage-repo). Agents use this plus forge/agent-policy.md and must not self-merge.
metadata:
  short-description: Open PRs; do not arm or apply Forge
---

# Dev PR（开发端）

You write code and draft Overlay files. You do **not** manage merge gates. Review and merge stay on **GitHub** ([`docs/rbac.md`](../../docs/rbac.md)). Product SOP: [`../use-forge/SKILL.md`](../use-forge/SKILL.md), [`../use-overlay/SKILL.md`](../use-overlay/SKILL.md). Agent rules: [`forge/agent-policy.md`](../../forge/agent-policy.md).

## Instructions

### Reuse — keep the tool out of the product commit repo

Do not `git add` `forge/`, `overlay/`, `schema/`, or `prompts/` into the product tree. 不要把工具上传到接入方要提交、推送的产品仓. Local CLI: sibling checkout + `PYTHONPATH`. CI: thin `uses:` pin. Details stay in `$use-forge` and `$use-overlay`.

### GitHub — land like everyone else

1. **Open a PR.** Do not push protected branches (`main` unless `forge.yaml` lists others). Do not force-push those branches.
2. **Request a human review.** CodeRabbit is advisory. It is never enough to merge by itself.
3. **Do not merge your own agent PRs.** Do not approve them. Do not write a review as `reviewed_by` on behalf of the model.
4. **Do not edit Rulesets, required checks, or CODEOWNERS** unless you are also the 管理端 — then switch to `$manage-repo`.
5. **Do not live `forge apply`.** No admin token on a developer laptop for apply. Dry-run only if a human asked and you are diagnosing; default is: do not run apply.
6. **Do not edit the adopter’s existing build workflow** (Learning Guide Verify is the first example).

### Overlay — draft only

7. **Write inbox and suites as `draft`.** One slice = one `inbox/<id>.md` = one `suites/<id>/`. Compile from adopter docs (`$use-overlay`, `$design-cases`). `function_id` is the adopter’s stable string.
8. **Do not arm.** Do not write `reviewed_by`. Do not write receipts. Do not flip `status` to `armed` or `blocked` unless you are the same human who is reviewing — that is `$manage-repo`.
9. **Fix armed-red.** If overlay-check failed on an already-`armed` `product_command`, fix **that** `function_id`’s code or command. Do not add process. Do not generate on push. Do not re-arm to “make it pass.”
10. **Leave `blocked` alone.** Not-ready features (payment/login fixtures) stay blocked so the job stays green. Do not promote them to armed.

### Agent extras (Copilot / Cursor)

11. Draft PR only. No self-approve. No self-merge. No Ruleset write. No Overlay arm. `generate` only when a human asked (not shipped). Dry-run Forge only if asked; never live apply.

### Never

- Do not vendor the tool into the product commit repo.
- Do not push protect. Do not self-merge. Do not self-approve.
- Do not live `forge apply`. Do not apply in Overlay CI.
- Do not arm, do not write `reviewed_by` / receipts.
- Do not change LearningGuidePortal Verify. Do not attach Proctor. Do not edit Deepseek3. Do not press `ilovelearningguide.com`.
- Do not generate on push. CI only; no CD.

## Examples

```text
# Developer machine — sibling tool checkout, product cwd
git switch -c cursor/fix-armed-select
# edit product code or suites/*/cases.md as draft
PYTHONPATH=../AIOps python3 -m overlay validate --root .
git push -u origin HEAD
# open PR on GitHub; request a human; do not merge
```

Illegal: `git push origin main`. Illegal: merge the agent PR you just opened. Illegal: `status: armed` in a suite you did not review as a human. Illegal: `python3 -m forge apply` without being 管理端.

## Performance Notes

No token on push. validate/select are local YAML. Fix the armed command that failed; do not start generate or apply.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想直推 main | 停。开 PR。 |
| 想合自己的 agent PR | 停。等人。Agent 不自 merge。 |
| armed check 红了 | 修那个 `function_id` 的代码或 `product_command`。不要改 Ruleset。 |
| 想把 draft 标 armed | 停。交给 `$manage-repo`（人或你换帽子手改 yaml）。 |
| 想 `forge apply` 省事 | 停。管理端 + admin token。你最多 `--dry-run`。 |
| 想把 overlay/ 拷进产品仓 | 停。`$use-overlay`。 |
| CodeRabbit 批了就想合 | 还要人 Approve + required checks（构建门，不是只有 CodeRabbit）。 |
| 支付/登录 suite 想 armed | 停。功能没就绪就 `blocked`，不当红。 |
