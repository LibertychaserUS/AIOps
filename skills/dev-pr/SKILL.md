---
name: dev-pr
description: Act as 开发端 (human developer) on a Forge-protected GitHub repo. This skill should be used when opening a PR, writing the PR brief (docs/pr-brief.md Conventional Commits title + six headings), requesting review, or fixing an armed Overlay failure. Do not use to apply Rulesets, merge-gate setup, live forge apply, or write reviewed_by / armed (use manage-repo). Agents use this plus forge/agent-policy.md and must not self-merge. Do not invent branch, workflow, or skill prefixes.
metadata:
  short-description: Open PRs; do not arm or apply Forge
---

# Dev PR（开发端）

You write code and draft Overlay files. You do **not** manage merge gates. Review and merge stay on **GitHub** ([`docs/rbac.md`](../../docs/rbac.md)). Product SOP: [`../use-forge/SKILL.md`](../use-forge/SKILL.md), [`../use-overlay/SKILL.md`](../use-overlay/SKILL.md). Agent rules: [`forge/agent-policy.md`](../../forge/agent-policy.md). PR 标题必须过 `python -m forge pr-title`（Conventional Commits `type(product/actor): subject`）：[`docs/pr-brief.md`](../../docs/pr-brief.md)。模板：[`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md)。

## Instructions

### Reuse — keep the tool out of the product commit repo

Do not `git add` `forge/`, `overlay/`, `schema/`, or `prompts/` into the product tree. 不要把工具上传到接入方要提交、推送的产品仓. Local CLI: sibling checkout + `PYTHONPATH`. CI: thin `uses:` pin. Details stay in `$use-forge` and `$use-overlay`.

### GitHub — land like everyone else

1. **Open a PR.** Title must pass `python -m forge pr-title --title "…"`. Grammar is Conventional Commits 1.0.0 with required scope `product/actor`: `type(product/actor): subject` (optional `!` before `:`). Types: Angular / commitlint conventional (`feat` `fix` `docs` `ci` `chore` `test` `refactor` `perf` `style` `build` `revert`). Product: `forge` \| `overlay` \| `ci` \| `docs`. Actor: `dev` \| `admin` \| `agent`（开发=`dev`，管理=`admin`）。Example: `feat(overlay/dev): add overlay run to overlay-check`. That `actor` is the **only** 分工 label — not a branch name, not a workflow name, not a skill name. Do **not** invent `[开发][Overlay]` or `dev feat(overlay):`. Leave `cursor/…` / `copilot/` (including `cursor/…-6842`) alone. Body keeps the six 解说规格 headings: `做了什么` `为什么` `动了哪些门` `怎么验` `不做什么` `分工`. The **分工** heading is who reviews/merges ([`docs/rbac.md`](../../docs/rbac.md)), not the title actor. Spec: [`docs/pr-brief.md`](../../docs/pr-brief.md). 开发写。管理拒收 `pr-title` 红或正文缺节的 PR。Do not push protected branches (`main` unless `forge.yaml` lists others). Do not force-push those branches.
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

12. Draft PR only. Title must pass `python -m forge pr-title`. Fill the six headings. No self-approve. No self-merge. No Ruleset write. No Overlay arm. `generate` only when a human asked (not shipped). Dry-run Forge only if asked; never live apply.

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
PYTHONPATH=../AIOps python3 -m forge pr-title --title "fix(overlay/dev): fix armed select"
git push -u origin HEAD
# open PR titled: fix(overlay/dev): fix armed select
# body: 做了什么 / 为什么 / 动了哪些门 / 怎么验 / 不做什么 / 分工
# request a human; do not merge
```

Illegal: `git push origin main`. Illegal: merge the agent PR you just opened. Illegal: `status: armed` in a suite you did not review as a human. Illegal: `python3 -m forge apply` without being 管理端. Illegal: branch `开发/overlay-fix` as a 分工 scheme. Illegal: title `[开发][Overlay] fix armed select`.

## Performance Notes

No token on push. validate/select are local YAML. Title lint is a regex. Fix the armed command that failed; do not start generate or apply.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想直推 main | 停。开 PR。 |
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

`pr-title` 红则不能合（Ruleset 勾上 `forge.yaml` `required_checks` 之后）。本地：`python -m forge pr-title --title "…"`。见 [`docs/pr-brief.md`](../../docs/pr-brief.md)。
