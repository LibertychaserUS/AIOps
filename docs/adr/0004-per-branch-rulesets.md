# 0004 按分支 Ruleset

- 状态：已接受
- 日期：2026-09-11

## 背景

v1 顶层 `required_checks` / `review.min_approvals` / `review.code_owners` 对 `protect` 里每个分支套同一规则。dev（集成、无人批）和 main（发布、要批 + CODEOWNERS）需要不同的门。一条 Ruleset 不够。

## 决定

`forge.yaml` 增加 `branches:` 表。出现时优先于顶层旧字段。旧字段继续接受，等价于对 `protect` 里每个分支套同一规则。

每个保护分支一条 Ruleset，名 `forge-protected-<branch>`，幂等（按名查、有则 PUT）。写入：`pull_request`（批准数、CODEOWNERS、新推作废旧审）、`required_status_checks`（strict）、`non_fast_forward`、`deletion`。

额外一条 tag Ruleset `forge-protected-tags`：`refs/tags/overlay-v*`、`refs/tags/forge-v*`（可配 `tag_patterns`），禁止快进 / 删除 / 更新。

`status` 读回每条：installed / missing / drifted。无 token 时写「未查询：缺 FORGE_GITHUB_TOKEN」。

`forbidden_live_repos` 读配置（默认空）；工作本自己写上不得 live-apply 的产品仓。主机名硬拒绝（生产域字符串）保留。

未知顶层键 → validate 红，并提示近邻拼写（例如 `deny_path` → `deny_paths`）。

## 后果

- `apply --dry-run` 打印全部 payload。
- 接入方 `required_checks` 仍是 **CI job 名**，按分支可以不同（dev 可以没有 `forge-check`，main 可以要）。
- 工作本 `title.scopes` 列出允许 scope；接入方可用 `any`（只查 Conventional Commits 语法）。

权威字段表见合入后的 `docs/forge-config.md`。CLI 行为见 [`docs/cli.md`](../cli.md)。

## 修订（2026-10-29）

`pull_request` 规则补齐书面契约里已经写明、但原先没锁的三个参数：

- `allowed_merge_methods` ← `branches.<name>.merge_methods`，默认 `[squash]`（「进保护分支默认 squash 封顶」）。
- `require_last_push_approval` ← `branches.<name>.last_push_approval`，默认 `approvals ≥ 1` 时 `true`：最后一推必须有人再批，agent 不能在批准后追加提交。
- `required_review_thread_resolution` ← `branches.<name>.resolve_threads`，默认 `false`。

同时每条 required check 带 `integration_id`（`checks_app_id`，默认 GitHub Actions `15368`）：同名 commit status 不再能顶替 Actions job。`required_checks` 为空的分支不写 `required_status_checks` 规则。这些默认值只把已写在文档里的契约落到 Ruleset，不新增接入方没同意的锁；三个分支键与 `checks_app_id` 都可显式改回。

## 替代方案

- 组织级 Ruleset 一次罩所有仓：以后再说，第一刀仓级。
- 人在 GitHub UI 手搭两条：允许，但 `apply` 是幂等标准件，避免漂移。
- 顶层字段与 `branches:` 同时生效后合并：否。`branches:` 出现则完全优先，避免半套规则。
