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

PR 规格机器检查是 `python -m forge pr-title`（`forge check` 嵌同一把锁）。来源按事件取，不是「空白就 skip」：

| 状态 | 来源 | 结果 |
|---|---|---|
| `--title` / `--body` 已给（含 `""`） | arg | lint；空参数仍红 |
| 非空 `PR_TITLE` / `PR_BODY` | env | lint |
| `GITHUB_EVENT_NAME=pull_request` 且标题/正文空白或未设 | 空 env | 标题红 `empty PR title`；有 `docs/pr-brief.md` 时正文红（缺六个标题） |
| `push`，或 Actions 把标题写成空串（环境已设、不是 `pull_request`） | HEAD 提交第一行 | lint 该 subject（事件 JSON `head_commit.message`，否则 `git log -1`） |
| 本地、无事件、环境未设 | 省略 | `forge check` skip 该步 |

CI job `pr-title` 仍只挂 `pull_request`。`forge check` 在 push 上**不**卸掉标题锁：锁的是提交 subject，不是跳过。叶子 `FN-forge-pr-title`，invariant `INV-pr-spec-event-states`。

## docs_sync

```yaml
docs_sync:
  - paths: [forge/**]
    require: [CHANGELOG.md, docs/forge-config.md]
```

`check` 相对 `origin/<protect[0]>` 的 merge-base（含工作区）计算 diff。命中 `paths` 却没有同时改动任一 `require` → 红。

内建三条（只扫 git 跟踪且未被 `.gitignore` 忽略的 `*.md`；`node_modules/`、构建产物不算）：

1. 仓内 `*.md` 相对链接目标必须存在。以 `/` 开头的链接视为站点根路径（Web 产品的 `public/`），不检查；`http(s)://`、`mailto:`、`#` 也不检查。
2. （仅工作本根）`*.md` 里出现的 `overlay-vX.Y.Z` / `forge-vX.Y.Z` 必须是已有 git tag，或 CHANGELOG 里 `## [overlay-X.Y.Z]` / `## [forge-X.Y.Z]`。允许写下一版，但要先登记。
3. 若 `docs/STATE.md` 存在，其保护分支 / required checks / CI job 名必须与当前 `forge.yaml` + `.github/workflows` 一致，否则红（「运行 forge status --write」）。pin / 最近 tag 只作记录，不参与比对（发布提交先带 STATE 再打 tag）。

## 内容包（按层配对）

内容包是进保护枝的那单 squash PR，不是功能枝上每一颗 WIP。决定：[ADR 0007](adr/0007-content-package-layers.md)。封顶拓扑见 [`pr-brief.md`](pr-brief.md)。

**不是**「每次都必须同时交文档 + 代码 + workflow」。  
**是**「碰哪一层，同单带上那一层的配对物；没碰的层不要塞进来」。

| 层 | 谁改 | 同单必须带 | 机器锁 |
|---|---|---|---|
| 工具 / 产品代码 | agent / 开发 | 命中 `docs_sync.paths` → 同改任一 `require` | `docs_sync` |
| 解说（标题 + 六标题正文） | 开 PR 的人 | 正文从 diff 写 | `pr-title` / `pr-body` |
| CI workflow | 人 / Ops（产品仓常在 `deny_paths`） | 已发布针存在之后才升 pin；job 名变了就 `forge status --write` | `deny_paths`；`status --check-state` |

五种包：产品包、工具包、文档包、工作流 / 升针包、升级包（`promote`）。不要把升针塞进功能切片。不要把「每个 agent PR 必须改 workflow」写成规则——产品仓把 `.github/workflows/` 放进 `deny_paths` 时，那样写等于每单都红，或把 deny 卸掉。

接入方示例（`examples/learning-guide/forge.yaml`）：套件 / 配置 → brief。工作本自己：`forge/**` → CHANGELOG + `docs/forge-config.md`。

## forbidden_live_repos

默认空。工作本自己的 `forge.yaml` 列出 `first-light-techhk/learningguideportal`。源码里另有一条对工作本产品仓生产域名的硬拒绝（`assert_apply_allowed`），与配置无关。不要把产品仓主机名写进通用说明。
