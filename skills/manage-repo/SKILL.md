---
name: manage-repo
description: Act as 管理端 (repo admin / maintainer) on GitHub-native review and merge. This skill should be used when applying a Forge Ruleset, setting required checks, writing CODEOWNERS, merging a green+approved PR, rejecting a PR that lacks the PR-name title prefix or six headings (docs/pr-brief.md), or arming/blocking an Overlay suite (`reviewed_by`). Admin PRs use title `[管理][<product>]`. Do not use to open a feature PR or fix armed-red as a developer (use dev-pr). Do not invent branch, workflow, or skill prefixes. Product install SOP stays in use-forge and use-overlay.
metadata:
  short-description: Admin Ruleset, merge, Overlay arm/block
---

# Manage Repo（管理端）

Review and merge live on **GitHub**. You are the human who installs the cage and writes Overlay receipts of review. There is no admin portal. RBAC: [`docs/rbac.md`](../../docs/rbac.md). Product SOP: [`../use-forge/SKILL.md`](../use-forge/SKILL.md), [`../use-overlay/SKILL.md`](../use-overlay/SKILL.md). PR 名分工只写标题前缀：[`docs/pr-brief.md`](../../docs/pr-brief.md)。标题前缀不是权限。模板：[`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md)。

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
   Token: `FORGE_GITHUB_TOKEN` or `GITHUB_TOKEN`, Administration: write. Humans run live apply. Agents do not.
2. **Set required checks in the GitHub Ruleset UI** (or the payload Forge applied). Use the adopter’s own job names (their build gate, plus `overlay-check` only if they installed Overlay). Forge does not create those jobs. CodeRabbit may be a check; it must **not** be the only merge gate.
3. **Paste CODEOWNERS / team names.** Copy wording from [`forge/CODEOWNERS.example`](../../forge/CODEOWNERS.example) into the product `.github/CODEOWNERS`. Put people in **GitHub org teams**. Do not build a local ACL file that GitHub will not enforce.
4. **Paste agent policy text** from [`forge/agent-policy.md`](../../forge/agent-policy.md) into the adopter `AGENTS.md`. Do not vendor `forge/`.
5. **Refuse a PR** whose **title** lacks `[<role>][<product>]` or whose body lacks any of the six 解说规格 headings ([`docs/pr-brief.md`](../../docs/pr-brief.md)). The title prefix is the only 分工 label; do not ask authors to rename branches, workflows, or skills. Body **分工** is who reviews/merges ([`docs/rbac.md`](../../docs/rbac.md)), not the prefix.
6. **Merge on GitHub** when required checks are green and the Ruleset approval count is met (default 1). You (or another human with write) click merge. Do not let an agent merge. Do not self-approve an agent PR you prompted if you are the only reviewer and the Ruleset needs a second human — get another person. The title prefix is not who may merge. If **you** open an admin/docs PR, title it `[管理][Forge|Overlay|CI|docs] …`. Leave `cursor/…` / `copilot/` alone.
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
- Do not invent role prefixes on branches, workflows, or skill names. 分工 = GitHub **PR 名（标题）前缀** only.
- Do not live-apply Forge in Overlay CI or to LearningGuidePortal.
- Do not change LearningGuidePortal Verify. Do not attach / run / gate intern-workspace Proctor. Do not edit Deepseek3. Do not press `ilovelearningguide.com`.
- Do not let CodeRabbit be the only required merge check.
- Do not let agents write `reviewed_by`, receipts, or `status: armed`.
- Do not generate on push. Do not implement a portal.
- Do not merge a PR that lacks the title prefix or the six headings.

## Examples

```text
# Install the cage (admin machine, sibling tool checkout)
PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/PRODUCT --path forge.yaml --dry-run
# Then live apply with an admin token. Then in GitHub: required checks = Verify + overlay-check.
# If you open a PR for the yaml/docs: title [管理][Forge] apply protected-default ruleset

# Overlay arm (hand yaml; review CLI does not write yet)
# suites/my-slice/suite.yaml → status: armed, reviewed_by: alice, reviewed_at: 2026-09-10T12:00:00Z, armed_reason: landing page ships
PYTHONPATH=../AIOps python3 -m overlay validate --root .
```

Merge: GitHub PR page, after the brief is present, checks green, and approval. Not Overlay. Not a custom 管理端.

## Performance Notes

`forge apply` is one GET + one POST/PUT. Overlay arm is a yaml edit + local `validate`. No model. Token only on explicit apply.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想做管理端网页管 merge | 停。GitHub Ruleset + 人点 merge。见 [`docs/rbac.md`](../../docs/rbac.md)。 |
| `overlay review` 不改文件 | 这一刀拒绝写盘。手改 `suite.yaml`。 |
| 想在 overlay-check 里 `forge apply` | 停。admin token 只在人本机或受保护的 dispatch。 |
| CodeRabbit 绿了就想当唯一门 | 停。勾接入方构建 check；Overlay 若已装再勾 overlay-check。 |
| Agent 开的 PR 没人 Approve | 人审。Agent 不得自 Approve、不得自 merge。 |
| 想用 `管理/` 当分支前缀 | 停。分工只写 PR 标题。分支仍 `cursor/` 或人的习惯名。 |
| 想把 `forge/` 拷进产品仓 | 停。`$use-forge`。 |
| 想对 LearningGuidePortal live apply | 停。fixture，不是试验场。 |
| 标题没有 `[开发][Overlay]` 这种前缀 | 拒收。让作者改 **PR 名**。不要改分支名。见 [`docs/pr-brief.md`](../../docs/pr-brief.md)。 |
| 正文缺「做了什么」等六节 | 拒收。用 [`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md)。 |
