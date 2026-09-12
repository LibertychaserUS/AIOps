# 变更日志

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

产品分两条线：`overlay-X.Y.Z` 与 `forge-X.Y.Z`。对应 git tag 为 `overlay-vX.Y.Z` / `forge-vX.Y.Z`。未发布的段写在下面，打 tag 时由 `forge release` 引用。

## [forge-1.1.3]

### Fixed

- PR 规格机器检查（`python -m forge pr-title` 与 `forge check` 的 pr-title / pr-body 步）把空白 `PR_TITLE` / `PR_BODY` 视为省略。GitHub Actions 在 `push` 上写 `github.event.pull_request.title` 会得到空串；`1.1.2` 把它当成「有标题」并报 `empty PR title`。没有规格就 skip，不红。显式 `--title ""` 仍红。

## [forge-1.1.2]

### Fixed

- `docs_sync` 的「版本引用必须是已有 tag」只在工作本根执行；接入方引用工具 tag（`overlay-v2.0.0`）不再被自己仓库没有该 tag 判红。

## [forge-1.1.1]

### Fixed


- `docs_sync` 只扫 git 跟踪且未忽略的 `*.md`；`node_modules/` 等不再被当成仓内文档。
- `docs_sync` 把以 `/` 开头的链接视为站点根路径（Web 产品 `public/`），不再当仓内相对路径报错。
- `status --check-state` 不再比对 pin / 最近 tag（发布提交先带 STATE 再打 tag 会自相矛盾），改为比对 CI job 名。
- `status` 的 CI job 名只取 `jobs.<id>.name`（或 job id），不再把 workflow `name:` 和 step `- name:` 算进去。
- `check` 在 `--root` 为 git 子目录（monorepo）时，diff 路径相对 `--root`，`deny_paths` 与 `suite_guard` 才对得上。

## [overlay-2.0.0]

### Added

- 状态机只保留 `active` | `blocked`（缺省 = `active`）。
- `python -m overlay migrate --root . [--dry-run]`：把 `draft`/`armed` 改成 `active`，删除 `reviewed_by` / `reviewed_at` / `armed_reason`。
- 套件 `schema: overlay-suite/v2`。配置仍是 `overlay-config/v1`。
- `blocked` 必须带非空 `blocked_reason`，且含链接或登记编号。
- `overlay run --timeout`；回执记录 `exit`、`duration_s`、命令 sha256。
- reusable workflow 的 `setup_command`（产品工具链）与 `runtime_setup` 文档示例。
- `select --branch` 缺省：`GITHUB_BASE_REF` → `GITHUB_REF_NAME` → `main`；未知分支回落到 `branches.default` 再到 `main`。

### Changed

- `never_red_statuses` 只接受 `blocked`。`select` 丢掉 blocked 时打印 reason。
- `forbid_hosts` 写明：只是字符串匹配，防手滑，不是安全边界。
- 叶子仍须 `### Functional` / `### Negative` / `### Edge`；`function_id` 全局唯一；invariant 对 `##` 标题。
- 权威契约改由中文 `docs/overlay-contract.md` 描述（合入后）。

### Removed

- 字段 `reviewed_by`、`reviewed_at`、`armed_reason`。出现即 validate 红。
- 状态 `draft`、`armed`。人签改走 PR 批准 + CODEOWNERS；隔离改走 `blocked` + 链接。见 [ADR 0002](docs/adr/0002-remove-armed.md)。

### 迁移

见 [`docs/migration-v2.md`](docs/migration-v2.md)。产品仓：`overlay migrate`，把 reusable `uses:` pin 到 `overlay-v2.0.0`（或该 SHA），`never_red_statuses` 去掉 `draft`。

## [forge-1.1.0]

### Added

- `forge.yaml` `branches:` 按保护分支写 `required_checks` / `approvals` / `code_owners` / `promote_from`。
- `forge promote --from <src> --to <dst>`：开或更新晋升 PR，永不 merge。
- `docs_sync` 表；`title.scopes`（`any` 或允许列表）；`forbidden_live_repos`（默认空）。
- `forge status --write docs/STATE.md`：生成中文状态页。
- `suite_guard`：agent 分支不得把套件改成 `blocked`。
- 工作本 CI job `unittest`（永远跑，不走 ci-select）。
- tag Ruleset `forge-protected-tags`。

### Changed

- 每个保护分支一条 Ruleset `forge-protected-<branch>`（不再共用一个 `forge-protected-default` 罩全部）。
- `submit` 默认 base = `protect[0]`；`--base` 必须在 `protect`。
- `check` 步骤含 overlay validate/cover、pr-title、pr-body、deny_paths、suite_guard、docs_sync、以及仅工作本的 sop-lock / schema / unittest。接入方根目录不打印 workshop-only skip。
- `title.scopes: any` 时只查 Conventional Commits 语法；工作本继续列出允许 scope。
- `release` 要求 CHANGELOG 有对应 `## [forge-X.Y.Z]` 段。

### Removed

- 源码常量 `FORBIDDEN_LIVE_REPOS`（改读配置）。
- `suite_arm`（改名并改为 `suite_guard`，不再看 `armed` / `reviewed_by`）。

### 迁移

见 [`docs/migration-v2.md`](docs/migration-v2.md)。把顶层 `required_checks` / `review` 改成 `branches:`；`protect` 第一项设为 submit 默认 base；加上 CODEOWNERS；CI pin `forge-v1.1.0`。

## [overlay-1.0.1] — 2026-09-10

tag `overlay-v1.0.1` 与 `forge-v1.0.1` 同一提交 `b4afc10ae0be4725e5109030f14a05bb2291fe4a`。

### Added

- 原生 CLI skills（`use-overlay` / `design-cases` 等）与 `gh skill install --pin` 路径。
- 产品前缀分治的 CI：`overlay-check` 与 Forge / 通用检查分文件。
- 中文 README 入口；pin 已发布 tag，不要 pin `main`。

### Changed

- 叶子三技法标题锁死为 Functional / Negative / Edge。
- squash 封顶 / 换底写进 SOP 与 `submit` base=`protect`。

### 来自 git

`git log --oneline overlay-v1.0.0..overlay-v1.0.1`：发布 1.0.1 与 native skills（#6）、workflow 前缀分治（#7）、Overlay CI 与 Conventional Commit 标题（#3）、以及一批 pin / README / skill frontmatter 文档提交。

## [forge-1.0.1] — 2026-09-10

同一提交。

### Added

- `python -m forge check` 本地代推门；`submit` 必须持有 `FORGE_SUBMIT_TOKEN`。
- `sop-lock`、`pr-title`、`ci-select`、`ops-review`、`bounce`、`release`。
- 改 `deny_paths` 则 `forge check` 红；agent 分支不得 arm/签字（v1 的 `suite_arm`）。

### Changed

- live `apply` / `release` 拒绝配置的产品仓；tag SHA 必须与将发的提交一致。
- 文档明确：Forge 是落地工具，不是测试工具；初始化要人明确同意。

## [overlay-1.0.0] — 2026-09-10

tag `overlay-v1.0.0` @ `235e514e673fa68b24879c8e139f2a5c6633ebb5`。

### Added

- `validate` / `select` / `run` / `cover` / 回执；状态 `draft` | `blocked` | `armed`。
- reusable `.github/workflows/overlay.yml`。
- Learning Guide fixture 在 `examples/learning-guide/`。

## [forge-1.0.0] — 2026-09-10

同一提交。

### Added

- `apply` / `status` / 默认 Ruleset JSON；`agent-policy` 模板。
- 保护 `main`：禁直推、必须 PR。
