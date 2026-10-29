# forge.yaml 配置

权威说明。字段名与 `schema: forge-config/v1` 一致。未知顶层键会红，并给出 did-you-mean。`ci`、`ci.products.<name>`、`ci.select` 下的未知键同样退出 3。文件由 PyYAML（safe loader）解析：任一层级重复的键退出 3（不再后写覆盖前写）；空文件退出 3（`empty document`）；语法错误一行报出并退出 3。不带引号的 `1.0`、`2026-01-01`、`yes` / `on` 一律按字符串读（分支名、check 名、tag 模式），只有 `true` / `false` 与整数按类型读。

## 全字段

| 字段 | 含义 | 默认 |
|---|---|---|
| `schema` | 必须是 `forge-config/v1` | 必填 |
| `protect` | 保护分支列表。**第一个**是 `submit` 的默认 base | `[main]` |
| `agent_branch_prefixes` | agent 分支前缀 | `[cursor/, copilot/]` |
| `deny_paths` | `check` 的 deny_paths 命中即红 | `.github/workflows/ci.yml` |
| `required_checks` | 旧字段：对每个 protect 分支套同一组 CI job 名 | `[]` |
| `review.min_approvals` / `review.code_owners` | 旧字段：对每个 protect 分支套同一审批 | `1` / `false` |
| `branches.<name>` | 按分支覆盖：`required_checks`、`approvals`、`code_owners`、`promote_from`、`merge_methods`、`last_push_approval`、`resolve_threads` | 逐键回落旧字段，再回落默认 |
| `title.scopes` | `any` 或允许的 `product/actor` 列表 | 缺省 = 现行 `product/actor` 语法 |
| `docs_sync` | 路径表：命中 `paths` 必须同时改任一 `require` | `[]` |
| `forbidden_live_repos` | live `apply` / `release` 拒绝的 `OWNER/NAME` | `[]` |
| `tag_patterns` | tag Ruleset 的 include | `[overlay-v*, forge-v*]` |
| `checks_app_id` | required checks 绑定的 GitHub App id（`integration_id`）；`null` / `none` 不绑 | `15368`（GitHub Actions） |
| `tag_rules.creation` | tag Ruleset 加 `creation` 规则 + 仓库 admin bypass（[ADR 0008](adr/0008-tag-creation-lock.md)，提议，opt-in） | `false` |
| `ci` | `ci-select` 选择器（通用检查 ≠ 产品门） | 可选 |

`branches:` 出现时优先于顶层 `required_checks` / `review`。旧字段继续接受，等价于给 `protect` 里每个分支套同一规则。优先是**逐键**的：`branches.<name>` 里没写的键取顶层旧字段的值（`required_checks` / `review.min_approvals` / `review.code_owners`），顶层也没写才取默认；只写 `code_owners: true` 的 `branches.main` 仍继承顶层 `required_checks` 与 `min_approvals`。见 [ADR 0004](adr/0004-per-branch-rulesets.md) 2026-10-29 修订。

`branches.<name>` 只认 `required_checks`、`approvals`、`code_owners`、`promote_from`、`merge_methods`、`last_push_approval`、`resolve_threads`；`review` 只认 `min_approvals`、`code_owners`；`tag_rules` 只认 `creation`。拼错（`aprovals`、`min_approval`）退出 3 并给 did-you-mean，不再静默回落默认。`branches:` 里的分支必须在 `protect` 里；`promote_from` 指向的分支也必须在 `protect` 里，且不能是自己。

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

| 分支键 | 写入 `pull_request` 参数 | 默认 |
|---|---|---|
| `required_checks` | `required_status_checks`（strict；空列表时**不写**这条规则并警告） | 顶层 `required_checks` |
| `approvals` | `required_approving_review_count` | `review.min_approvals` |
| `code_owners` | `require_code_owner_review` | `review.code_owners` |
| `merge_methods` | `allowed_merge_methods`（`merge` / `squash` / `rebase` 的非空子集） | `[squash]` |
| `last_push_approval` | `require_last_push_approval` | `approvals ≥ 1` 时 `true`，否则 `false` |
| `resolve_threads` | `required_review_thread_resolution` | `false` |

`merge_methods` 默认只放 squash，与「进保护分支默认 squash 封顶」一致（[ADR 0004](adr/0004-per-branch-rulesets.md) 修订）。要放开 merge commit 或 rebase 的仓显式写 `merge_methods: [squash, merge]`。

`submit` 只推检查过的提交：`--head` 必须是当前检出分支（不收 `HEAD`、`heads/`、`refs/`、`tags/`），工作树必须干净（含未跟踪文件），推送用 `<sha>:refs/heads/<head>`。更新已有 PR 只改标题，不动正文。`FORGE_GITHUB_API` 必须是 https（仅 `127.0.0.1` / `localhost` 可 http）。

`apply` 为每个保护分支写一条 Ruleset，名 `forge-protected-<branch>`，幂等按名 PUT。另写 `forge-protected-tags`，保护 `refs/tags/overlay-v*` 与 `refs/tags/forge-v*`（可配 `tag_patterns`）：禁止更新 / 删除 / 非快进；`tag_rules.creation: true` 时再加 `creation`，并给仓库 admin 一条 `bypass_actors`（见 [ADR 0008](adr/0008-tag-creation-lock.md)，提议；默认关）。`--dry-run` 打印全部 payload。`status` 逐条报告 installed / missing / drifted；GitHub 上还有、但已不对应任何 `protect` 分支的 `forge-protected-*`（`forge-protected-tags` 除外）另报 `stale`。`apply` 也列出 stale，但**不删**；要删去 GitHub 设置页手动删。

`apply` / `status` 的非致命警告写 stderr、不改退出码：某分支 `code_owners: true` 但目标根下没有 `.github/CODEOWNERS`、`CODEOWNERS`、`docs/CODEOWNERS` 任一；某保护分支 `required_checks` 为空（此时不写 `required_status_checks` 规则，而不是写一条空 contexts）。`apply` 的目标根取 `--path` 所在目录（省略 `--path` 时取 cwd）；`status` 取 `--root`。

### required checks 绑定 Actions app（`checks_app_id`）

每条 required check 都带 `integration_id`，默认 `15368`（GitHub Actions app）。不绑时，任何有 write 权限的人都能 POST 一条同名 commit status（如 `unittest`）满足 Ruleset；绑上后只认 Actions 跑出来的同名 job。工作本与两个示例的 required checks 全是 Actions job，默认值不会卡住任何人。

- check 来自别的 App（Jenkins、Buildkite 等）：写那个 App 的 id，`checks_app_id: 123456`。
- 混用或不想绑：`checks_app_id: null`（或 `none`），回到只按名字匹配。

装过旧版的仓，`status` 会把每条分支 Ruleset 报成 drifted（`integration_id` 参与比对），重新 `apply` 一次即回 installed。

drifted 按整条 payload 比：`name`、`target`、`enforcement`、`bypass_actors`、`conditions.ref_name.include` / `exclude`、规则类型集合、Forge 写入的每个规则参数（含 `require_last_push_approval`、`allowed_merge_methods`、`required_review_thread_resolution`），以及 required checks 的 `context` + `integration_id`（排序后比，顺序不算漂移）。忽略 GitHub 生成的 `id`、`source`、`source_type`、`node_id`、时间戳、`_links`、`current_user_can_bypass`，以及 Forge 没写、GitHub 回显默认值的参数。被停用（`disabled` / `evaluate`）、加了 bypass、加了 exclude 的 Ruleset 报 drifted，不再报 installed。

`apply` / `status` 列 Ruleset 时带 `includes_parents=false` 并按 `Link: rel="next"` 翻完所有页；只认 `source_type` 为 `Repository`（缺该字段视为本仓）的条目。组织级同名 Ruleset 不会被当成本仓的去 PUT。

`status --path` 指向不存在的文件退出 3（与 `apply` 同）。省略 `--path` 时读 `<root>/forge.yaml`，不读 cwd；不存在则用默认值。`status --check-state` 逐行比对 STATE.md 的「保护分支」行（required_checks、approvals、code_owners、promote_from），任一不一致即红。

drifted 时逐字段列差异（终端与 `docs/STATE.md` 同样带）：`enforcement: expected active, live disabled`、`bypass_actors: -{...}`、`ref_name.exclude: -refs/heads/x`、`rule deletion: expected, live missing`、`pull_request.required_approving_review_count: expected 1, live 0`、`required checks: +unit -lint`（`+` 应有而无，`-` 多出）。取单条 Ruleset 详情失败是 API 错误（退出 4），不算 drifted。

`status --strict`：任一预期 Ruleset（每条 `protect` 分支的 `forge-protected-<branch>` 与 `forge-protected-tags`）missing / drifted 时退出 2（与 `--check-state` 过期同码：check 红），stderr 列出哪条、什么状态；缺 token 退出 2 并点名 `FORGE_GITHUB_TOKEN`。不传 `--strict` 时只报告、退出 0。工作本 CI 装好 Ruleset 之前不要在 `forge-check.yml` 里加 `--strict`，否则必红。

GitHub 客户端（`apply` / `status` / `submit` / `promote` / `release` / `ops-review` / `bounce` 共用）：幂等 GET 遇 5xx / 429 最多 3 次（1s、2s 退避；`Retry-After` 优先，封顶 30s），写请求永不重试；限流 403（`X-RateLimit-Remaining: 0` 或正文 `rate limit`）与 429 报「rate limit hit … resets at <X-RateLimit-Reset>」退出 4，真正的 401 / 403 才是退出 2；跨主机重定向去掉 `Authorization`，https → http 拒绝，生产域名守卫对重定向目标同样生效。`apply` 创建时收到 422（同名已存在）按名重查并改 PUT。

## title.scopes

- `any`：只查 Conventional Commits 语法（type、可选 scope、冒号空格）。
- 列表：`type(product/actor): subject`，且 scope 必须在列表里。列表就是允许集：接入方可以写工作本以外的产品 / 角色（如 `infra/dev`），列出即通过。每一项必须是 `[a-z][a-z0-9-]*/[a-z][a-z0-9-]*`，否则读配置时退出 3 并指出那一项（`illegal title.scopes item: 'Infra/dev'`）。
- 缺省：`type(product/actor): subject`，product 限 `forge|overlay|ci|docs`，actor 限 `dev|admin|agent`。

三种模式共用同一组 subject 规则：整行 ≤ 72 字符；subject 至少含一个可见字符（空白与零宽字符 U+200B / U+200C / U+200D / U+2028 / U+2029 / U+FEFF 不算）；不以 `.` 或 `。` 结尾；单行、首尾无空白。

本工作本列出允许 scope，保留现在行为。接入方可写 `any`。

`forge promote` 的标题：列表里有 `ci/agent`，或 `scopes: any` 时，用 `chore(ci/agent):`。`ci` 让两扇产品门都跑。封闭列表没有 `ci/agent` 时用第一项，避免写出调用方没允许的 scope。

`promote` 只走配置好的晋升：目标分支必须有 `branches.<to>.promote_from`，`--from` 必须等于它且在 `protect` 里；否则退出 3（没有 `promote_from` 就不走晋升）。仓在 `forbidden_live_repos` 或源码硬拒名单里也退出 3。

当前 git 分支命中 `agent_branch_prefixes`，或解析不出当前分支（detached HEAD 且无 `GITHUB_HEAD_REF` / `GITHUB_REF_NAME`）时，live `promote` 拒绝（退出 3）。`--dry-run` 仍要 `FORGE_SUBMIT_TOKEN`，但不写 GitHub。人 / ops 分支行为不变。分工仍是 Ruleset + 人合入；agent 只开草稿。

PR 规格机器检查是 `python -m forge pr-title`（`forge check` 嵌同一把锁）。来源按事件取，不是「空白就 skip」：

| 状态 | 来源 | 结果 |
|---|---|---|
| `--title` / `--body` 已给（含 `""`） | arg | lint；空参数仍红 |
| 非空 `PR_TITLE` / `PR_BODY` | env | lint |
| `GITHUB_EVENT_NAME=pull_request` 且标题/正文空白或未设 | 空 env | 标题红 `empty PR title`；有 `docs/pr-brief.md` 时正文红（缺六个标题） |
| `push`，或 Actions 把标题写成空串（环境已设、不是 `pull_request`） | HEAD 提交第一行 | lint 该 subject（事件 JSON `head_commit.message`，否则 `git log -1`）。HEAD 是合并提交（两个以上父提交，如把 dev 并进功能分支）时，lint first-parent 上最近一个非合并提交的 subject；合并提交本身不算改动 |
| 本地、无事件、环境未设 | 省略 | `forge check` skip 该步 |

CI job `pr-title` 仍只挂 `pull_request`。`forge check` 在 push 上**不**卸掉标题锁：锁的是提交 subject，不是跳过。叶子 `FN-forge-pr-title`，invariant `INV-pr-spec-event-states`。

`forge check --root` 必须是产品根：至少有 `forge.yaml` 或 `overlay.yaml`。两者都没有 → 退出 2，不要当成绿。`pip install -r requirements.txt` 装 PyYAML，以及工作本风格门 ruff（`unittest` 里跑，不是新的 CI job）。**不会** 给出 `forge` 命令；用 `PYTHONPATH` + `python3 -m forge`。Overlay 与 Forge 是两针：`overlay-v2.0.0` / `forge-v1.1.3`。只 checkout Overlay 针会拿到 Forge 1.1.0（空根假绿）。`1.1.2` 上 CI `push` 不要写入空的 `PR_TITLE`；`1.1.3` 起 lock 提交 subject。

工作本 `forge check` 跑与 CI 相同的 `python -m unittest discover -s tests -t .`。没有 `overlay/__init__.py` 的接入方根不跑这套单测。

`ci-select`：产品门在标题选中它，**或**变更路径命中 `ci.products.<name>.paths` 时跑。标题 `docs` 不能挡住已经碰到的产品 diff。未声明的检查名仍是 skip-success。变更路径取 `HEAD~1..HEAD`，相对 `--root`（monorepo 子目录同 `check`），`--no-renames`：把文件移出产品目录仍选中该产品。算不出变更路径（浅克隆没有 `HEAD~1`、没有 git）时全部产品都跑，有标题也一样。

`pr-title` 读不了 `forge.yaml`（解析失败、字段非法）时退出 3，不会悄悄退回默认 scope 语法。

`apply` 必须带 `--path` 指向**目标仓自己的** `forge.yaml`。不要在工具仓根目录对产品仓 `--repo` live apply：cwd 的工作本配置会把 `pr-title` / `sop-lock` / `unittest` 写进别人的 Ruleset。`--dry-run` 同样要带 `--path` 才能对照。接入方最小例是 [`examples/acme-python/forge.yaml`](../examples/acme-python/forge.yaml)，不要抄工作本根 `forge.yaml`。

## docs_sync

```yaml
docs_sync:
  - paths: [forge/**]
    require: [CHANGELOG.md, docs/forge-config.md]
```

`check` 相对 `origin/<protect[0]>` 的 merge-base 计算 diff：已提交（merge-base..HEAD）、暂存区、工作区、未跟踪文件取并集。暂存一次回退不能藏住已提交的改动。命中 `paths` 却没有同时改动任一 `require` → 红。

**看不到 base 就红。** 按顺序找 `origin/<name>`、本地 `<name>`（`protect` 逐个），最后 `origin/$GITHUB_BASE_REF`。都没有（单分支克隆、远端不叫 `origin`、CI 浅检出）→ `deny_paths`、agent 枝的 `suite_guard`、有表时的 `docs_sync` 红，提示 `git fetch origin <protect[0]>`。不再退回只比 HEAD 的假绿。

`suite_guard` 认不出分支名（detached HEAD 且没有 `GITHUB_HEAD_REF` / `GITHUB_REF_NAME`）时按 agent 枝处理。`run_check(head_branch=...)` 可显式给出 head。

路径列表一律用 `git -z`：非 ASCII 路径（`secret/密钥.txt`、`suites/中/suite.yaml`）不会被 `core.quotePath` 转义成漏网的 `"\345..."`。

### 路径写法（`deny_paths` 与 `docs_sync.paths` 共用）

| 写法 | 含义 | 例 |
|---|---|---|
| 普通路径 | 等于该文件，或以它为目录前缀 | `docs/locked` 命中 `docs/locked/a.md` |
| 结尾 `/` | 目录前缀 | `secret/` |
| `*` / `?` / `[...]` | 只在一段内匹配，不跨 `/` | `src/*.py` 不命中 `src/a/b.py` |
| `**/` | 零或多层目录 | `forge/**/*.py` 命中 `forge/x.py` 与 `forge/a/b.py` |
| 结尾 `/**` | 该目录及其下全部 | `forge/**` |
| 不含 `/` 的 glob | 任意深度按文件名匹配（gitignore 规则） | `*.pem` 命中 `a/b/key.pem` |

glob 命中一个目录时，目录下的文件一并命中。路径相对 `--root`，开头的 `/`、`./` 忽略。

内建三条（只扫 git 跟踪且未被 `.gitignore` 忽略的 `*.md`；`node_modules/`、构建产物不算）：

1. 仓内 `*.md` 相对链接目标必须存在。以 `/` 开头的链接视为站点根路径（Web 产品的 `public/`），不检查；`http(s)://`、`mailto:`、`#` 也不检查。
2. （仅工作本根）`*.md` 里出现的 `overlay-vX.Y.Z` / `forge-vX.Y.Z` 必须是已有 git tag，或 CHANGELOG 里 `## [overlay-X.Y.Z]` / `## [forge-X.Y.Z]`。允许写下一版，但要先登记。
3. 若 `docs/STATE.md` 存在，其保护分支 / required checks / CI job 名必须与当前 `forge.yaml` + `.github/workflows` 一致，否则红（「运行 forge status --write」）。pin / 最近 tag 只作记录，不参与比对（发布提交先带 STATE 再打 tag）。

## 内容包（按层配对）

内容包是进保护枝的那单 squash PR，不是功能枝上每一颗 WIP。**提议**：[ADR 0007](adr/0007-content-package-layers.md)（未接受。先设计后实现：人接受前不加新的 `docs_sync` / CLI / workflow）。封顶拓扑见 [`pr-brief.md`](pr-brief.md)。一开始只有 0005 的配对锁，没有内容包规格；本表是补设计。

**不是**「每次都必须同时交文档 + 代码 + workflow」。  
**是**「碰哪一层，同单带上那一层的配对物；没碰的层不要塞进来」。

| 层 | 谁改 | 同单必须带 | 机器锁 |
|---|---|---|---|
| 工具 / 产品代码 | agent / 开发 | 命中 `docs_sync.paths` → 同改任一 `require` | `docs_sync` |
| 解说（标题 + 六标题正文） | 开 PR 的人 | 正文从 diff 写 | `pr-title` / `pr-body` |
| CI workflow | 人 / Ops（产品仓常在 `deny_paths`） | 已发布针存在之后才升 pin；job 名变了就 `forge status --write` | `deny_paths`；`status --check-state` |

五种包：产品包、工具包、文档包、工作流 / 升针包、升级包（`promote`）。不要把升针塞进功能切片。不要把「每个 agent PR 必须改 workflow」写成规则——产品仓把 `.github/workflows/` 放进 `deny_paths` 时，那样写等于每单都红，或把 deny 卸掉。

接入方最小例：[`examples/acme-python/forge.yaml`](../examples/acme-python/forge.yaml)。Learning Guide 夹具（`examples/learning-guide/forge.yaml`）是产品 job 名，不要当通用模板抄。工作本自己：`forge/**` → CHANGELOG + `docs/forge-config.md`。

## forbidden_live_repos

默认空。工作本自己的 `forge.yaml` 列出 `first-light-techhk/learningguideportal`。`apply` / `release` / `promote` 都查这张表（大小写不敏感）。源码里另有一条对工作本产品仓生产域名的硬拒绝（`assert_apply_allowed`），与配置无关。不要把产品仓主机名写进通用说明。

live `apply` / `release` / `promote` 总是**同时**检查配置列表与源码内置的 `FORBIDDEN_REPOS`（`forge/__init__.py`），大小写不敏感。用目标仓自己的 `forge.yaml`（常为 `[]`）或不带 `--path` 时，内置禁仓照样拒绝。

条目先规范化：去掉 `https://github.com/`、`github.com/` 前缀，去掉末尾 `.git` 与 `/`，转小写。规范化后仍不是 `OWNER/NAME` 的条目退出 3。不带引号的 URL（`- https://github.com/o/n`）按 YAML 规则是字符串，直接可用；加不加引号都行。
