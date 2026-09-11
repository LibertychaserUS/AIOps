# 0002 删除 `armed` / `reviewed_by`

- 状态：已接受
- 日期：2026-09-11

## 背景

Overlay v1 的套件状态是 `draft` | `blocked` | `armed`。`armed` 同时干了两份活：

1. **人签过字**：`reviewed_by` + `reviewed_at` + `armed_reason` 表示「有人审过、声称可测」。Agent 被禁止代签。
2. **解禁进门**：`select` 只纳入 `armed`；`draft` / `blocked` 丢掉且不当红（隔离未就绪功能，避免支付/登录一类必红集推进门）。

这两份活叠在同一个字段上，导致：agent 分支一旦把 `status` 写成 `armed` 就会进 CI；人审签名和 GitHub 上的 PR 批准脱节；`reviewed_by` 是第二套权限账本。v1 用 `suite_arm` 挡住 agent 改状态，但契约仍把「谁批准」写在 yaml 里。

## 决定

v2 状态只允许 **`active` | `blocked`**。缺省 = `active`。删除 `reviewed_by`、`reviewed_at`、`armed_reason`。旧值 `draft` / `armed` 在 `validate` 红，并提示运行 `python -m overlay migrate --root .`。

`armed` 的两份活分别替换为：

| 旧职责 | 谁接 |
|---|---|
| 人签过字（human sign-off） | **GitHub PR 批准 + CODEOWNERS**。用例页和 `suite.yaml` 随代码走 PR。Ruleset 的 `required_approving_review_count` 与 `require_code_owner_review` 按分支配置（见 [0004](0004-per-branch-rulesets.md)）。Agent 不自 Approve、不自 merge。 |
| 隔离未就绪（quarantine） | **`status: blocked`**，且 `blocked_reason` 非空，必须含链接或登记编号（`http(s)://…` 或 `OF-12` / `#123`）。`select` 丢掉 `blocked` 并打印 reason。`never_red_statuses` 只接受 `blocked`。 |

Agent 分支上，把套件从非 `blocked` 改成 `blocked` 由 `suite_guard` 红掉（人的分支只记录）。解禁（`blocked` → `active`）是人在保护分支路径上的 PR，走批准 + CODEOWNERS。

迁移：`overlay migrate` 把 `draft`/`armed` 改成 `active`，`blocked` 保留；删除旧审核字段；`blocked` 缺 reason 时不改、打印待办。

## 后果

- 不再有「CI 自动 armed」或「模型写 `reviewed_by`」这条攻击面：字段不存在。
- 未就绪功能仍不当红，但必须留下可点开的隔离理由。
- 人审用例的证据在 GitHub PR / CODEOWNERS，不在 yaml。
- 工作本自己的套件用 `overlay migrate` dogfood；`blocked` 的两条补 reason 链接（指向 ADR 或 CHANGELOG）。

## 替代方案

- 保留三态，只把 `armed` 改名 `active`：仍把人签写在 yaml，拒绝。
- 用 Overlay CLI `review --i-am` 当唯一签字：仍是第二套权限，拒绝。
- 未就绪用 `draft` 丢掉：v2 删除 `draft`，隔离一律 `blocked` + 链接。
