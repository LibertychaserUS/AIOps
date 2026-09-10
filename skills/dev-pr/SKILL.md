---
name: dev-pr
description: Act as 开发端 (human developer) on a Forge-protected GitHub repo. This skill should be used when submitting a PR via python -m forge submit (代推), writing the PR brief (docs/pr-brief.md Conventional Commits title + six headings), requesting review, or fixing an armed Overlay failure. Do not use to apply Rulesets, merge-gate setup, live forge apply, merge, or write reviewed_by / armed (use manage-repo). Agents use this plus forge/agent-policy.md and must not self-merge. Do not invent branch, workflow, or skill prefixes.
metadata:
  short-description: Open PRs; do not arm or apply Forge
---

# Dev PR（开发端）

You write code and draft Overlay files. You do **not** manage merge gates. Review and merge stay on **GitHub** ([`docs/rbac.md`](../../docs/rbac.md)). Product SOP: [`../use-forge/SKILL.md`](../use-forge/SKILL.md), [`../use-overlay/SKILL.md`](../use-overlay/SKILL.md). Agent rules: [`forge/agent-policy.md`](../../forge/agent-policy.md). PR 标题必须过 `python -m forge pr-title`（Conventional Commits `type(product/actor): subject`）：[`docs/pr-brief.md`](../../docs/pr-brief.md)。模板：[`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md)。

## Instructions

### Reuse — keep the tool out of the product commit repo

Do not `git add` `forge/`, `overlay/`, `schema/`, or `prompts/` into the product tree. 不要把工具上传到接入方要提交、推送的产品仓. Local CLI: sibling checkout + `PYTHONPATH`. CI: thin `uses:` pin. Details stay in `$use-forge` and `$use-overlay`.

### GitHub — land like everyone else

1. **Submit a draft PR with Forge** (开发侧代推). Do not `git push` a protect branch. Do not merge.
   ```text
   PYTHONPATH=../AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(overlay/dev): fix armed select" --dry-run
   PYTHONPATH=../AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(overlay/dev): fix armed select"
   ```
   `--dry-run` prints the intended remote branch, PR title, and the six body headings; no push; exit 0. Live submit (token present) pushes the feature branch and opens/updates a **draft** PR. Aligns with [`gh pr create`](https://cli.github.com/manual/gh_pr_create). Title must pass `python -m forge pr-title`. Grammar: Conventional Commits `type(product/actor): subject` ([`docs/pr-brief.md`](../../docs/pr-brief.md)). Example: `feat(overlay/dev): add overlay run to overlay-check`. Body headings: `做了什么` `为什么` `动了哪些门` `怎么验` `不做什么` `分工`. 开发写。管理拒收 `pr-title` 红或正文缺节的 PR。Do not push protected branches. Do not force-push those branches. Do not self-merge.
2. **Lock the title locally** with `python -m forge pr-title --title "…"` before you ask for review. Do not install husky to block `git commit`.
3. **Request a human review.** CodeRabbit is advisory. It is never enough to merge by itself.
4. **Do not merge your own agent PRs.** Do not approve them. Do not write a review as `reviewed_by` on behalf of the model.
5. **Do not edit Rulesets, required checks, or CODEOWNERS** unless you are also the 管理端 — then switch to `$manage-repo`.
6. **Do not live `forge apply`.** No admin token on a developer laptop for apply. Dry-run only if a human asked and you are diagnosing; default is: do not run apply.
7. **Do not edit the adopter’s existing build workflow** (Learning Guide Verify is the first example).

### Overlay — draft only

8. **Write inbox and suites as `draft`.** One slice = one `inbox/<id>.md` = one `suites/<id>/`. Compile from adopter docs (`$use-overlay`, `$design-cases`). `function_id` is the adopter’s stable string.
9. **Do not arm.** Do not write `reviewed_by`. Do not write receipts. Do not flip `status` to `armed` or `blocked` unless you are the same human who is reviewing — that is `$manage-repo`.
10. **Fix armed-red.** If overlay-check failed on an already-`armed` `product_command`, fix **that** `function_id`’s code or command. Do not add process. Do not generate on push. Do not re-arm to “make it pass.”
11. **Leave `blocked` alone.** Not-ready features (payment/login fixtures) stay blocked so the job stays green. Do not promote them to armed.

### Agent extras (Copilot / Cursor)

12. Draft PR only, via `forge submit`. Title must pass `python -m forge pr-title`. Fill the six headings. No self-approve. No self-merge. No Ruleset write. No Overlay arm. `generate` only when a human asked (not shipped). `submit --dry-run` is fine; never live apply.

### Never

- Do not vendor the tool into the product commit repo.
- Do not invent role prefixes on branches, workflows, or skill names. 分工 = GitHub PR 标题 `actor` only.
- Do not invent a private `[开发][Overlay]` title language.
- Do not push protect. Do not self-merge. Do not self-approve.
- Do not live `forge apply`. Do not apply in Overlay CI.
- Do not arm, do not write `reviewed_by` / receipts.
- Do not change LearningGuidePortal Verify. Do not attach Proctor. Do not edit Deepseek3. Do not press `ilovelearningguide.com`.
- Do not generate on push. CI only; no CD.
- Do not open a PR that fails `pr-title` or lacks the six headings.
- Do not add mandatory husky / npm commit hooks on this workshop.

## Examples

```text
# Developer machine — sibling tool checkout, product cwd
git switch -c cursor/fix-armed-select
# edit product code or suites/*/cases.md as draft
PYTHONPATH=../AIOps python3 -m overlay validate --root .
PYTHONPATH=../AIOps python3 -m forge submit --repo OWNER/NAME --title "fix(overlay/dev): fix armed select" --dry-run
PYTHONPATH=../AIOps python3 -m forge submit --repo OWNER/NAME --title "fix(overlay/dev): fix armed select"
# request a human; do not merge
```

Illegal: `git push origin main`. Illegal: `forge submit` on `main`. Illegal: merge the agent PR you just opened. Illegal: `status: armed` in a suite you did not review as a human. Illegal: `python3 -m forge apply` without being 管理端. Illegal: branch `开发/overlay-fix` as a 分工 scheme. Illegal: title `[开发][Overlay] fix armed select`.

## Performance Notes

No token on push. validate/select are local YAML. Title lint is a regex. Fix the armed command that failed; do not start generate or apply.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想直推 main | 停。`forge submit --dry-run`，再 submit。 |
| 想合自己的 agent PR | 停。等人。Agent 不自 merge。 |
| armed check 红了 | 修那个 `function_id` 的代码或 `product_command`。不要改 Ruleset。 |
| `pr-title` 红了 | 改 **PR 名** 为 `type(product/actor): subject`。本地先跑 `python -m forge pr-title --title "…"`。不要改分支名。 |
| 想把 draft 标 armed | 停。交给 `$manage-repo`（人或你换帽子手改 yaml）。 |
| 想 `forge apply` 省事 | 停。管理端 + admin token。你最多 `--dry-run`。 |
| 想用 `开发/` 当分支前缀 | 停。分工只写 PR 标题 actor。分支仍 `cursor/` 或人的习惯名。 |
| 想写 `[开发][Overlay]` | 停。那是私有语言。用 `feat(overlay/dev): …`。 |
| 想把 overlay/ 拷进产品仓 | 停。`$use-overlay`。 |
| CodeRabbit 批了就想合 | 还要人 Approve + required checks（构建门 + 已勾的 `pr-title`，不是只有 CodeRabbit）。 |
| 支付/登录 suite 想 armed | 停。功能没就绪就 `blocked`，不当红。 |
| 想写散文标题 | 停。`type(product/actor): subject` 一行。见 [`docs/pr-brief.md`](../../docs/pr-brief.md)。 |
| 管理说缺规格 | 按 [`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md) 补六节。 |
| 想装 husky 挡 commit | 停。本工作本不强制 commit hook。合并锁是 GitHub `pr-title`。 |

## Lock（不绿不能合）

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

- 标题 `type(product/actor): subject` + 正文六节：`python -m forge pr-title` → CI **`pr-title`**
- 代推 dry-run / protect 拒绝：`python -m forge submit --dry-run` + Forge 单测 → **`overlay-check`**
- armed 红：修那个 `function_id`，门仍是 **`overlay-check`**
- 仓级 SOP：`python -m forge sop-lock` → **`sop-lock`**（若已装）
- 不绿不能合。不要装 husky。不要自合。
