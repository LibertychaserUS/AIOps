---
name: manage-repo
description: >-
  Human maintainer actions — review Overlay suites (status blocked with reason),
  merge when required checks are green, promote dev to main, write STATE.md.
  Do not forge submit for developers (use dev-pr). Agents must not use this
  skill to apply Rulesets or merge.
metadata:
  short-description: Human review, merge, promote; live apply is Ops
---

# Manage Repo（管理端）

审和合在 **GitHub**。Agent 不得用本 skill 合 PR 或 live-apply Ruleset。路径：[`docs/dev-main-flow.md`](../../docs/dev-main-flow.md)。配置：[`docs/forge-config.md`](../../docs/forge-config.md)。

## Instructions

1. **Apply Forge with an admin token**，不要从 Overlay CI 跑 live apply。
   ```text
   PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/NAME --path forge.yaml --dry-run
   PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/NAME --path forge.yaml
   PYTHONPATH=../AIOps python3 -m forge status --repo OWNER/NAME --root . --write docs/STATE.md
   ```
   Token：`FORGE_GITHUB_TOKEN` 或 `GITHUB_TOKEN`。这把钥匙不是 `FORGE_SUBMIT_TOKEN`。每个保护分支一条 `forge-protected-<branch>`，另加 `forge-protected-tags`。
2. **Required checks** 是 PR 上的 **CI job 名**。本工作本：`overlay-check`、`pr-title`、`forge-check`、`sop-lock`、`unittest`。`dev` 无人批；`main` 要 1 个 approvals + CODEOWNERS（见 `branches:`）。**通用检查 ≠ 产品门。**
3. **Merge** 只在那些检查绿、审批够。默认 squash：**封顶**再压，压完**换底**。不要让 agent merge。不要替开发 `forge submit`（那是 `$dev-pr`）。
4. **Promote：** `dev` → `main` 由 `forge promote --repo O/N --from dev --to main` 开 PR。人批 + 合。命令本身永不 merge。
5. **Overlay `blocked`** 是人手改 yaml。Agent 不得在 agent 分支上做（`suite_guard` 红）。`blocked` 必须有带链接或编号的 `blocked_reason`。不要写已删除的旧字段。改完：`python -m overlay validate --root .`。
6. **发布：** `python -m forge release --repo OWNER/NAME --products overlay --version 2.0.0 --dry-run` 与 `--products forge --version 1.1.0` 分两次（`--products both` 要求两产品 `__version__` 相同）。CHANGELOG 必须有 `## [overlay-2.0.0]` / `## [forge-1.1.0]`。不要 force-move 已有针。

## Never

- 不要 vendor 工具。
- 不要让 agent 合 PR 或 live-apply。
- 不要 `forge submit` 替开发。
- 不要把 CodeRabbit 当唯一合入门。
- 不要合 `pr-title` / `sop-lock` / `overlay-check` / `forge-check` / `unittest` 红的 PR。

## Examples

```text
PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/PRODUCT --path forge.yaml --dry-run
PYTHONPATH=../AIOps python3 -m forge promote --repo OWNER/PRODUCT --from dev --to main --dry-run
PYTHONPATH=../AIOps python3 -m forge status --repo OWNER/PRODUCT --root . --write docs/STATE.md
```

合入：GitHub PR 页，squash，检查绿（`overlay-check`、`pr-title`、`forge-check`、`sop-lock`、`unittest`），人批。封顶再压，压完换底。

## Performance Notes

`forge apply` 是按名 GET + POST/PUT。Overlay `blocked` 是 yaml 编辑 + 本地 validate。无模型。

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想替开发 push / submit / check | 停。开发自己 check + 持 `FORGE_SUBMIT_TOKEN`。Ops 只审**合入** + merge。 |
| `promote` 想顺手 merge | 停。命令永不 merge。 |
| Agent 代写 `blocked` | 拒收。自己写 reason 链接。 |
| required_checks 抄了别人的 workflow 名 | 改回本仓 job 名。 |
| STATE 不新鲜 | `forge status --write docs/STATE.md`。 |
| 想发下一版 tag | CHANGELOG 先有对应 `## [product-X.Y.Z]`，再 `release --dry-run`。不要 force-move。 |

## Lock（不绿不能合）

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

本工作本 Ruleset 必须勾：`overlay-check`、`pr-title`、`forge-check`、`sop-lock`、`unittest`。这些是 **合入锁**。**通用检查 ≠ 产品门。** 开发侧提交前的本地门是 `python -m forge check` 绿 **并且** 持有 `FORGE_SUBMIT_TOKEN`（**代推锁**）。进保护分支默认 squash：**封顶**再压，压完**换底**。不绿不能合。不 live-apply Rulesets（除非 Ops 明确对非禁仓执行）。
