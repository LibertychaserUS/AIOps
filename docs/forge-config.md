# forge.yaml 配置

权威说明。字段名与 `schema: forge-config/v1` 一致。未知顶层键会红，并给出 did-you-mean。

## 全字段

| 字段 | 含义 | 默认 |
|---|---|---|
| `schema` | 必须是 `forge-config/v1` | 必填 |
| `protect` | 保护分支列表。**第一个**是 `submit` 的默认 base | `[main]` |
| `agent_branch_prefixes` | agent 分支前缀 | `[cursor/, copilot/]` |
| `deny_paths` | `check` 的 deny_paths 命中即红 | `.github/workflows/ci.yml` |
| `required_checks` | 旧字段：对每个 protect 分支套同一组 CI job 名 | `[]` |
| `review.min_approvals` / `review.code_owners` | 旧字段：对每个 protect 分支套同一审批 | `1` / `false` |
| `branches.<name>` | 按分支覆盖：`required_checks`、`approvals`、`code_owners`、`promote_from` | 无则回落旧字段 |
| `title.scopes` | `any` 或允许的 `product/actor` 列表 | 缺省 = 现行 `product/actor` 语法 |
| `docs_sync` | 路径表：命中 `paths` 必须同时改任一 `require` | `[]` |
| `forbidden_live_repos` | live `apply` / `release` 拒绝的 `OWNER/NAME` | `[]` |
| `tag_patterns` | tag Ruleset 的 include | `[overlay-v*, forge-v*]` |
| `ci` | `ci-select` 选择器（通用检查 ≠ 产品门） | 可选 |

`branches:` 出现时优先于顶层 `required_checks` / `review`。旧字段继续接受，等价于给 `protect` 里每个分支套同一规则。

## 按分支规则

```yaml
protect: [dev, main]
branches:
  dev:
    required_checks: [unit, lint, overlay-check]
    approvals: 0
    code_owners: false
  main:
    required_checks: [unit, lint, overlay-check, forge-check]
    approvals: 1
    code_owners: true
    promote_from: dev
```

`apply` 为每个保护分支写一条 Ruleset，名 `forge-protected-<branch>`，幂等按名 PUT。另写 `forge-protected-tags`，保护 `refs/tags/overlay-v*` 与 `refs/tags/forge-v*`（可配 `tag_patterns`）。`--dry-run` 打印全部 payload。`status` 逐条报告 installed / missing / drifted。

## title.scopes

- `any`：只查 Conventional Commits 语法（type、可选 scope、冒号空格、subject 非空、长度 ≤ 72、不以句号结尾）。
- 列表：现行 `type(product/actor): subject`，且 scope 必须在列表里。

本工作本列出允许 scope，保留现在行为。接入方可写 `any`。

## docs_sync

```yaml
docs_sync:
  - paths: [forge/**]
    require: [CHANGELOG.md, docs/forge-config.md]
```

`check` 相对 `origin/<protect[0]>` 的 merge-base（含工作区）计算 diff。命中 `paths` 却没有同时改动任一 `require` → 红。

内建三条：

1. 仓内 `*.md` 相对链接目标必须存在。
2. `*.md` 里出现的 `overlay-vX.Y.Z` / `forge-vX.Y.Z` 必须是已有 git tag，或 CHANGELOG 里 `## [overlay-X.Y.Z]` / `## [forge-X.Y.Z]`。允许写下一版，但要先登记。
3. 若 `docs/STATE.md` 存在，其保护分支 / required checks / 最近 tag 必须与当前 `forge.yaml` + git 一致，否则红（「运行 forge status --write」）。

## forbidden_live_repos

默认空。工作本自己的 `forge.yaml` 列出 `first-light-techhk/learningguideportal`。源码里另有一条对工作本产品仓生产域名的硬拒绝（`assert_apply_allowed`），与配置无关。不要把产品仓主机名写进通用说明。
