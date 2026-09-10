---
name: dev-pr
description: Act as 开发端 (human developer) on a Forge-protected GitHub repo. This skill should be used when running python -m forge check (local pre-submit gate), submitting a PR via python -m forge submit (代推; check must be green), writing the PR brief (docs/pr-brief.md Conventional Commits title + six headings), requesting review, or fixing an armed Overlay failure. Do not use to apply Rulesets, merge-gate setup, live forge apply, merge, or write reviewed_by / armed (use manage-repo). Agents use this plus forge/agent-policy.md and must not self-merge. Do not invent branch, workflow, or skill prefixes.
metadata:
  short-description: Open PRs; do not arm or apply Forge
---

# Dev PR（开发端）

You write code and draft Overlay files. You do **not** manage merge gates. Review and merge stay on **GitHub** ([`docs/rbac.md`](../../docs/rbac.md)). Product SOP: [`../use-forge/SKILL.md`](../use-forge/SKILL.md), [`../use-overlay/SKILL.md`](../use-overlay/SKILL.md). Agent rules: [`forge/agent-policy.md`](../../forge/agent-policy.md). **提交前**必须 `python -m forge check` 绿 **并且** 宿主已注入写权限；缺任一则不 push、不开 PR（`--dry-run` 同样 fail closed）。PR 标题必须过 `python -m forge pr-title`（Conventional Commits `type(product/actor): subject`）：[`docs/pr-brief.md`](../../docs/pr-brief.md)。模板：[`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md)。

## Instructions

### Reuse — keep the tool out of the product commit repo

Do not `git add` `forge/`, `overlay/`, `schema/`, or `prompts/` into the product tree. 不要把工具上传到接入方要提交、推送的产品仓. Local CLI: sibling checkout + `PYTHONPATH`. CI: thin `uses:` pin. Details stay in `$use-forge` and `$use-overlay`.

### GitHub — land like everyone else

1. **Run the local pre-submit gate first.** 不绿则不 push、不开 PR。`forge submit`（含 `--dry-run`）会先跑同一道门，红则拒绝。
   ```text
   PYTHONPATH=../AIOps python3 -m forge check --root . --title "feat(overlay/dev): fix armed select"
   ```
   有 `overlay.yaml` 时跑 `overlay validate` + `overlay cover`；有 `--title` 时跑 `pr-title`（submit 必须过标题）；工具仓有 `schema/` 时跑 `schema/check.py`；本工作本有 `tests/` 时跑快单测子集。打印清单。退出 `0` 绿、`2` 红。不写 GitHub。不用模型。可选包装（不默认安装）：`forge/hooks/pre-submit`。不要装 husky / npm。
2. **Submit a draft PR with Forge** (开发侧代推). Do not `git push` a protect branch. Do not merge.
   ```text
   PYTHONPATH=../AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(overlay/dev): fix armed select" --dry-run
   PYTHONPATH=../AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(overlay/dev): fix armed select"
   ```
   `--dry-run` 先跑 `forge check`；红则退出 2。check 绿后仍必须已有宿主注入的写权限（PAT / fine-grained / GitHub App token）。缺或空：退出 2，打印 `credential: <source>` / `no usable GitHub write credential`，不 push。人用 `gh auth login`，代理用宿主注入，不回落 `GITHUB_TOKEN` 或 Ops 的 `FORGE_GITHUB_TOKEN`。密钥在且 check 绿：打印计划 + `credential: <source>`；不 push。永不打印 token 值。Live 同样先 check，再 push 功能分支并开/更新 **draft** PR。永不 merge / approve / arm。Aligns with [`gh pr create`](https://cli.github.com/manual/gh_pr_create) **consuming host-injected git/gh credential**. Title must pass `python -m forge pr-title`. Grammar: Conventional Commits `type(product/actor): subject` ([`docs/pr-brief.md`](../../docs/pr-brief.md)). Example: `feat(overlay/dev): add overlay run to overlay-check`. Body headings: `做了什么` `为什么` `动了哪些门` `怎么验` `不做什么` `分工`. 开发写。管理拒收 `pr-title` 红或正文缺节的 PR。Do not push protected branches. Do not force-push those branches. Do not self-merge. Ops merge 用另一套权限，不是这把提交密钥。
3. **Lock the title locally** with `python -m forge pr-title --title "…"` (also inside `forge check`) before you ask for review. Do not install husky to block `git commit`.
4. **Request a human review.** CodeRabbit is advisory. It is never enough to merge by itself.
5. **Do not merge your own agent PRs.** Do not approve them. Do not write a review as `reviewed_by` on behalf of the model.
6. **Do not edit Rulesets, required checks, or CODEOWNERS** unless you are also the 管理端 — then switch to `$manage-repo`.
7. **Do not live `forge apply`.** No admin token on a developer laptop for apply. Dry-run only if a human asked and you are diagnosing; default is: do not run apply.
8. **Do not edit the adopter’s existing build workflow** (Learning Guide Verify is the first example).

### Overlay — draft only

9. **Write inbox and suites as `draft`.** One slice = one `inbox/<id>.md` = one `suites/<id>/`. Compile from adopter docs (`$use-overlay`, `$design-cases`). `function_id` is the adopter’s stable string.
10. **Do not arm.** Do not write `reviewed_by`. Do not write receipts. Do not flip `status` to `armed` or `blocked` unless you are the same human who is reviewing — that is `$manage-repo`.
11. **Fix armed-red.** If overlay-check failed on an already-`armed` `product_command`, fix **that** `function_id`’s code or command. Do not add process. Do not generate on push. Do not re-arm to “make it pass.”
12. **Leave `blocked` alone.** Not-ready features (payment/login fixtures) stay blocked so the job stays green. Do not promote them to armed.

### Agent extras (Copilot / Cursor)

13. Draft PR only, via `forge submit`. `python -m forge check` must be green first (submit runs it). You must hold 宿主注入的写权限. Use the host-injected login (`gh auth login` / `GH_TOKEN` / extraheader). Title must pass `python -m forge pr-title`. Fill the six headings. No self-approve. No self-merge. No Ruleset write. No Overlay arm. `generate` only when a human asked (not shipped). Missing token: `--dry-run` is still red. Never live apply.

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
- Do not `forge submit` (dry-run or live) when `python -m forge check` is red. 不绿不 push、不开 PR。
- Do not `forge submit` without 宿主注入的写权限. Do not fall back to `GITHUB_TOKEN` / `gh auth`.
- Do not add mandatory husky / npm commit hooks on this workshop.

## Examples

```text
# Developer machine — sibling tool checkout, product cwd
git switch -c cursor/fix-armed-select
# edit product code or suites/*/cases.md as draft
PYTHONPATH=../AIOps python3 -m forge check --root . --title "fix(overlay/dev): fix armed select"
# requires 宿主注入的写权限 (even --dry-run)
PYTHONPATH=../AIOps python3 -m forge submit --repo OWNER/NAME --title "fix(overlay/dev): fix armed select" --dry-run
PYTHONPATH=../AIOps python3 -m forge submit --repo OWNER/NAME --title "fix(overlay/dev): fix armed select"
# request a human; do not merge
```

Illegal: `git push origin main`. Illegal: `forge submit` on `main`. Illegal: `forge submit` when `forge check` is red. Illegal: `forge submit` without 宿主注入的写权限. Illegal: merge the agent PR you just opened. Illegal: `status: armed` in a suite you did not review as a human. Illegal: `python3 -m forge apply` without being 管理端. Illegal: branch `开发/overlay-fix` as a 分工 scheme. Illegal: title `[开发][Overlay] fix armed select`.

## Performance Notes

Overlay 模型 token 不在 push 上花。Forge 代推必须另持 宿主注入的写权限。validate/select are local YAML. Title lint is a regex. Fix the armed command that failed; do not start generate or apply.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想直推 main | 停。先 `python -m forge check`，再 `forge submit --dry-run`，再 submit。 |
| `forge check` 红了 | 停。不 push、不开 PR。按清单修红项。 |
| 缺 宿主注入的写权限 | 停。`--dry-run` 也红。不要用 `GITHUB_TOKEN` / `gh auth` 凑。Ops merge 不是这把钥匙。 |
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
| 想装 husky 挡 commit | 停。本工作本不强制 commit hook。代推锁是 `python -m forge check`；合入锁是 GitHub required checks。 |

## Lock（不绿不能合）

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

- **代推锁（提交前）：** `python -m forge check` 必须绿 **并且** 宿主已注入写权限。缺密钥或 check 红：`forge submit`（含 `--dry-run`）拒绝，不 push、不开 PR。CI `GITHUB_TOKEN` 是合入锁，不是代推。Ops merge 是另一套权限。
- 标题 `type(product/actor): subject` + 正文六节：`python -m forge pr-title`（也在 check 里）→ CI **`pr-title`**（合入锁）
- 代推 dry-run / protect 拒绝：`python -m forge submit --dry-run` + Forge 单测 → **`forge-check`**（合入锁）
- Overlay armed 红：修那个 `function_id`，门仍是 **`overlay-check`**
- 仓级 SOP：`python -m forge sop-lock` → **`sop-lock`**（**通用**合入锁，永远跑；不是 forge-check 的一层）
- GitHub required checks 锁**合入**，不锁提交。本地 check + 宿主注入的写权限（`gh auth login` / `GH_TOKEN` / extraheader） 锁**代推**。**通用检查 ≠ 产品门。** 产品门按 `forge.yaml` 选跑或跳过。不绿不能提交。不绿不能合。不要装 husky。不要自合。
