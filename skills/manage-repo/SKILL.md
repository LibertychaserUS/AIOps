---
name: manage-repo
description: Act as 管理端 (repo admin / maintainer) on GitHub-native review and merge. Ops only: review required checks (合入锁) and merge when green. Local python -m forge check is the 开发侧 代推锁 — Ops does not run it for developers. This skill should be used when applying a Forge Ruleset, setting required checks, writing CODEOWNERS, merging a green+approved PR, rejecting a PR that fails pr-title or lacks the six headings (docs/pr-brief.md), or arming/blocking an Overlay suite (`reviewed_by`). Do not push or forge submit for developers (use dev-pr). Do not invent branch, workflow, or skill prefixes. Product install SOP stays in use-forge and use-overlay.
metadata:
  short-description: Admin Ruleset, merge, Overlay arm/block
---

# Manage Repo（管理端）

Review and merge live on **GitHub**. You are the human who installs the cage and writes Overlay receipts of review. There is no admin portal. RBAC: [`docs/rbac.md`](../../docs/rbac.md). Product SOP: [`../use-forge/SKILL.md`](../use-forge/SKILL.md), [`../use-overlay/SKILL.md`](../use-overlay/SKILL.md). PR 标题必须过检查 **`pr-title`**（`python -m forge pr-title`，Conventional Commits）：[`docs/pr-brief.md`](../../docs/pr-brief.md)。标题 `actor` 不是权限。模板：[`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md)。

## Instructions

Stay imperative. Do not invent a second permission database.

### Reuse — keep the tool out of the product commit repo

Do not vendor `forge/`, `overlay/`, `schema/`, or `prompts/` into the adopter product git. 不要把工具上传到接入方要提交、推送的产品仓. Full reuse steps: `$use-forge`, `$use-overlay`. Product repo: thin `forge.yaml` / `overlay.yaml` + inbox/suites + a workflow that `uses:` this repo at a **tag or SHA**. Local CLI: `PYTHONPATH` to a sibling checkout of this workshop or a fork.

### GitHub — the only merge control plane

1. **Apply Forge with an admin token**, never from Overlay CI, never to `First-Light-TechHK/LearningGuidePortal`.
   ```text
   PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/NAME --path forge.yaml --dry-run
   PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/NAME --path forge.yaml
   PYTHONPATH=../AIOps python3 -m forge status --repo OWNER/NAME
   ```
   Token: `FORGE_GITHUB_TOKEN` or `GITHUB_TOKEN`, Administration: write. Humans run live apply. Agents do not. This apply token is **not** the submit path. Submit requires `FORGE_SUBMIT_TOKEN`. Do not live-apply Forge Rulesets from an agent.
2. **Set required checks in the GitHub Ruleset UI** (or the payload Forge applied). Use the adopter’s own job names (their build job, plus `overlay-check` only if they installed Overlay, plus `pr-title` if they installed the title workflow, plus `sop-lock` if they installed the SOP workflow). This workshop lists `overlay-check`, `pr-title`, `forge-check`, and `sop-lock` in `forge.yaml`. Forge does not create those jobs. CodeRabbit may be a check; it must **not** be the only merge gate.
3. **Paste CODEOWNERS / team names.** Copy wording from [`forge/CODEOWNERS.example`](../../forge/CODEOWNERS.example) into the product `.github/CODEOWNERS`. Put people in **GitHub org teams**. Do not build a local ACL file that GitHub will not enforce.
4. **Paste agent policy text** from [`forge/agent-policy.md`](../../forge/agent-policy.md) into the adopter `AGENTS.md`. Do not vendor `forge/`.
5. **Refuse a PR** whose **title** fails `python -m forge pr-title` or whose body lacks any of the six 解说规格 headings ([`docs/pr-brief.md`](../../docs/pr-brief.md)). The title `actor` is the only 分工 label; do not ask authors to rename branches, workflows, or skills. Body **分工** is who reviews/merges ([`docs/rbac.md`](../../docs/rbac.md)), not the title actor.
6. **Merge on GitHub** when required checks are green and the Ruleset approval count is met (default 1). Default landing is **squash**（封顶再压）。After squash, the next branch starts from the new `main` SHA（换底）. Do not merge a PR whose base is another unmerged `cursor/` head. Overlay Ops order on a selected PR is already: spec → CodeRabbit/Copilot comments → full Overlay CI. You only click merge after that chain is green. If spec/CI is red or merge fails, the PR is **打回** (`bounce` comment); open the run’s `overlay-ops-debug` / receipts artifacts and debug — do not invent a second tracker. **Do not merge if `overlay-check`, `pr-title`, `forge-check`, or `sop-lock` is red.** Do not let an agent merge. Do not self-approve an agent PR you prompted if you are the only reviewer and the Ruleset needs a second human — get another person. **Do not `forge submit` or push a developer’s branch for them** — that is `$dev-pr`. The title `actor` is not who may merge. If **you** open an admin/docs PR, title it `feat(forge/admin): …` or `docs(docs/admin): …` and run `python -m forge pr-title --title "…"`. Leave `cursor/…` / `copilot/` alone.
7. **Do not open a second constitution.** No SaaS admin, no OAuth app, no RBAC API. Bypass stays empty in the default Ruleset; if you add bypass, do it in the GitHub UI, not in Overlay.

### Overlay — humans arm or block

8. **Write `reviewed_by` yourself.** Agents must not. CI must not. Forge must not.
9. **This slice’s review CLI refuses writes.** Even with `--i-am HUMAN`:
   ```text
   PYTHONPATH=../AIOps python3 -m overlay review --suite ID --status armed --i-am YOUR-HANDLE --reason TEXT
   ```
   It records that you are human and exits non-zero without editing yaml. **Hand-edit** `suites/<id>/suite.yaml`:
   - `status: armed` or `blocked`
   - non-empty `reviewed_by` + ISO-8601 `reviewed_at`
   - `armed_reason` if armed; `blocked_reason` if blocked
10. **Arm** only when the leaf is reviewed and claimed testable (`product_command` if it should gate). **Block** when reviewed but the feature is not ready (payment/login fixtures). `draft` stays unreviewed.
11. Validate after the edit (`PYTHONPATH` to the tool checkout). `blocked` / `draft` must not redden overlay-check.

### Never

- Do not vendor the tool into the product commit repo.
- Do not invent role prefixes on branches, workflows, or skill names. 分工 = GitHub PR 标题 `actor` only.
- Do not invent a private `[开发][Overlay]` title language.
- Do not merge when `overlay-check`, `pr-title`, `forge-check`, or `sop-lock` is red.
- Do not live-apply Forge in Overlay CI or to LearningGuidePortal.
- Do not change LearningGuidePortal Verify. Do not attach / run / gate intern-workspace Proctor. Do not edit Deepseek3. Do not press `ilovelearningguide.com`.
- Do not let CodeRabbit be the only required merge check.
- Do not let agents write `reviewed_by`, receipts, or `status: armed`.
- Do not generate on push. Do not implement a portal.
- Do not merge a PR that fails `pr-title` or lacks the six headings.
- Do not `forge submit` or push on behalf of 开发端. Ops = checks + merge only.
- Do not add mandatory husky / npm as the merge lock.

## Examples

```text
# Install the cage (admin machine, sibling tool checkout)
PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/PRODUCT --path forge.yaml --dry-run
# Then live apply with an admin token. Then in GitHub: required checks = Verify + overlay-check + pr-title + forge-check + sop-lock (if installed).
# If you open a PR for the yaml/docs: title feat(forge/admin): apply protected-default ruleset
# Local: python3 -m forge pr-title --title "feat(forge/admin): apply protected-default ruleset"

# Overlay arm (hand yaml; review CLI does not write yet)
# suites/my-slice/suite.yaml → status: armed, reviewed_by: alice, reviewed_at: 2026-09-10T12:00:00Z, armed_reason: landing page ships
PYTHONPATH=../AIOps python3 -m overlay validate --root .
```

Merge: GitHub PR page, squash, after the brief is present, checks green (`overlay-check`、`pr-title`、`forge-check`、`sop-lock`), and approval. 封顶再压，压完换底. Not Overlay. Not a custom 管理端.

## Performance Notes

`forge apply` is one GET + one POST/PUT. Title lint is a regex. Overlay arm is a yaml edit + local `validate`. No model. Token only on explicit apply.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想替开发 push / `forge submit` / `forge check` | 停。开发侧自己 check + 持有非空 `FORGE_SUBMIT_TOKEN` 再 submit。Ops 只审合入检查 + merge。合入权限不是那把提交密钥。 |
| 想做管理端网页管 merge | 停。GitHub Ruleset + 人点 merge。见 [`docs/rbac.md`](../../docs/rbac.md)。 |
| `overlay review` 不改文件 | 这一刀拒绝写盘。手改 `suite.yaml`。 |
| 想在 overlay-check 里 `forge apply` | 停。admin token 只在人本机或受保护的 dispatch。 |
| CodeRabbit 绿了就想当唯一门 | 停。勾接入方构建 check；Overlay 若已装再勾 overlay-check；Forge CI 已装再勾 `forge-check`；标题 workflow 已装再勾 `pr-title`；SOP workflow 已装再勾 `sop-lock`。 |
| `pr-title` 红了还想合 | 停。拒收。让作者改 PR 名。见 [`docs/pr-brief.md`](../../docs/pr-brief.md)。 |
| Agent 开的 PR 没人 Approve | 人审。Agent 不得自 Approve、不得自 merge。 |
| 想用 `管理/` 当分支前缀 | 停。分工只写 PR 标题 actor。分支仍 `cursor/` 或人的习惯名。 |
| 标题是 `[管理][Forge] …` | 拒收。改成 `feat(forge/admin): …`。 |
| 想把 `forge/` 拷进产品仓 | 停。`$use-forge`。 |
| 想对 LearningGuidePortal live apply | 停。fixture，不是试验场。 |
| 正文缺「做了什么」等六节 | 拒收。用 [`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md)。 |

## Lock（不绿不能合）

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

本工作本 Ruleset 必须勾：`overlay-check`、`pr-title`、`forge-check`、`sop-lock`（`forge.yaml` `required_checks`）。这些是 **合入锁**。**通用检查 ≠ 产品门。** `pr-title` / `sop-lock` 永远跑；产品门按 `forge.yaml` `ci` 选跑或跳过成功。Overlay Ops PR 链（选中时）：规格 → CodeRabbit/Copilot 评论 → 全量 Overlay CI → 人合；红则 `bounce` 打回并留 `ops-debug`。红则不能合。开发侧提交前的本地门是 `python -m forge check` 绿 **并且** 持有 `FORGE_SUBMIT_TOKEN`（**代推锁**；`gh auth` 不够）；Ops 不替开发跑 check / submit。进 `main` 默认 squash：PR 必须是整段工作的**封顶**；合完**换底**。不要从即将被压掉的旧头再叠。CodeRabbit 不能当唯一门。人审：谁点 merge；GitHub UI 是否把 base 指到未合的 `cursor/` 枝。不绿不能合。不 live-apply Rulesets。
