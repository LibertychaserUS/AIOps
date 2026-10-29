# 变更日志

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

产品分两条线：`overlay-X.Y.Z` 与 `forge-X.Y.Z`。对应 git tag 为 `overlay-vX.Y.Z` / `forge-vX.Y.Z`。未发布的段写在下面，打 tag 时由 `forge release` 引用。

## [Unreleased]

### Added

- `python -m overlay generate`：假 HTTP 可测；缺 API key 退出 3；解析失败不写文件；输出 `status: active`。`blocked` 套件拒绝，`--force` 也不清掉 `blocked`。不挂 push。提示词 `prompts/extract.md`、`prompts/generate-cases.md`（temperature 0）。
- `overlay review` 在 `--i-am` 非空且当前分支不是 agent 前缀时写套件状态。没有 `forge.yaml` 拒绝。agent 分支不能借此清掉 `blocked`。
- `overlay.yaml` 可选 `require_command`（缺省 false）。为 true 时，入选套件没有 `product_command` 则 `run` 退出 2、不执行。
- `forge status --strict`：任一预期 Ruleset（含 `forge-protected-tags`）missing / drifted 退出 2（与 `--check-state` 同码）；缺 token 退出 2 并点名 `FORGE_GITHUB_TOKEN`，不再默默打印「未查询」。不传 `--strict` 行为不变。
- `forge status` 的 drifted 逐字段列差异（`enforcement`、`bypass_actors`、`ref_name.include/exclude`、规则有无、规则参数、`required checks: +应有 -多出`），终端与 `docs/STATE.md` 都带。
- `sop-lock`（仅工作本根）：`.github/CODEOWNERS` 必须存在且给 `suites/**`、`forge.yaml`、`overlay.yaml` 指定 owner。分支前缀只是约定，CODEOWNERS + Ruleset 才是锁。工作本 CODEOWNERS 补上 `forge.yaml @LibertychaserUS`。
- `forge.yaml` 顶层 `checks_app_id`（默认 `15368` = GitHub Actions）：每条 required check 带 `integration_id`，同名 commit status 不能顶替 Actions job；`null` / `none` 不绑。
- `branches.<name>.merge_methods`（默认 `[squash]`）、`last_push_approval`（默认 `approvals ≥ 1` 时 true）、`resolve_threads`（默认 false），写入 `allowed_merge_methods` / `require_last_push_approval` / `required_review_thread_resolution`。见 [ADR 0004](docs/adr/0004-per-branch-rulesets.md) 修订。
- `tag_rules.creation`（默认 **false**，opt-in）：tag Ruleset 加 `creation` 并给仓库 admin 一条 bypass。[ADR 0008](docs/adr/0008-tag-creation-lock.md)（提议，未接受；工作本不开）。
- `status` 把 GitHub 上多出来、不对应任何 `protect` 分支的 `forge-protected-*` 报 `stale`；`apply` 也列出，不删。
- `apply` / `status`：`code_owners: true` 但没有 `.github/CODEOWNERS` / `CODEOWNERS` / `docs/CODEOWNERS` 时警告（stderr，不改退出码）。

### Fixed

- `forge check` / `pr-title` 在 `push` 事件上：HEAD 是合并提交（把保护分支并进功能分支）时，改 lint first-parent 上最近的非合并提交 subject，不再因 `Merge branch 'dev' into …` 报红；功能提交 subject 不合规仍红。
- GitHub 客户端：幂等 GET 遇 5xx / 429 最多重试 3 次（1s、2s 退避；有 `Retry-After` 按其秒数，封顶 30s）；POST / PUT / PATCH / DELETE 永不重试。
- GitHub 客户端：`X-RateLimit-Remaining: 0` 或正文含 `rate limit` 的 403 报限流（退出 4，附 `X-RateLimit-Reset` 的重置时间），不再误报「auth failed」。
- GitHub 客户端：跨主机重定向去掉 `Authorization`；https 跳 http 拒绝；生产域名守卫同样适用于重定向目标，不只看第一个 URL。
- `forge status` 取 Ruleset 详情失败时报 API 错误（退出 4），不再回落到列表项后误报 drifted。
- `forge apply` 创建 Ruleset 收到 422（同名已存在）时按名重查并 PUT 到已有 id，不再直接退出 4。假 GitHub 对重名 POST 也返回 422。
- `ci-select` 新增真实 git 单测：移出产品的重命名、根提交（无 `HEAD~1` → 全跑）、`--root` 子目录、非 ASCII 路径。

- `overlay.yaml` 按 `schema/overlay-config.schema.json` 校验：未知 key（如拼错的 `require_comand`）报错退出 2，不再静默回落默认值。
- 三件套检查：代码围栏里的 `##` / `### Functional` 不再算结构；每个技法段必须有非空正文才算覆盖。
- `overlay review` / `migrate`：改写前对比改前改后的解析结果，只允许目标 key 变化（review：`status`、`blocked_reason`；migrate：`schema`、`status`、旧字段），否则拒写并留作待办；写入改为临时文件加原子替换。
- `forbid_hosts` 按主机边界匹配：裸域名、子域名、`user@host` 都算命中，`example.com` 不再误中 `example.community`；inbox 正文仍只查 URL。`run` 先检查全部入选命令，任一命中则一条都不启动（回执记 `not_started`）。
- 可复用工作流 `overlay.yml`：接入方未传 `tool_ref` 直接失败（`github.workflow_sha` 是调用方的提交）；总是先装 `_aiops/requirements.txt`，调用方自己的 `requirements.txt` 不再把 PyYAML 挤掉。`docs/overlay-ci.md` 所有示例补上 `tool_ref`。
- `overlay generate --force`：保留原有的 `product_command`（不再重置为 null），`trace.yaml` 存在时提示可能过期。
- `overlay run`：子进程 `PYTHONPATH` 去掉指向工具仓自身的那一项，产品命令不再意外 import 到 `overlay` / `forge`；`--timeout` 必须大于 0，`0` 不再静默改成 600。
- `docs/overlay-contract.md` 新增退出码表（0/2/3/4/5）。
- 工作本 `unittest` 与 `forge-check` 两个 job 的 checkout 改为 `fetch-depth: 0`，让 `forge check` 在 CI 里看得到 `origin/dev`（缺基准时现在按设计变红）。
- `overlay review`：`--reason "#123"` 这类登记号写成带引号的 YAML，不再被当成注释读成 null。`--suite` 必须是合法套件 id，`../` 不能改到 `suites/` 外的文件。
- `overlay generate`：`packages` 逐项加引号，`@acme/web` 这类 scoped 包名不再写出解析不了的 `suite.yaml`。
- `overlay migrate`：`status: "draft"`、`status: draft  # 注释` 也会改成 `active`，不再报改写成功却留下旧状态。
- `overlay validate`：`status` 不是字符串（如 `[blocked]`）时报 `illegal status` 退出 2，不再抛 TypeError。
- `overlay run`：命令在自己的进程组里跑，超时杀整棵进程树并打印已有输出；stdin 接 `/dev/null`；非 UTF-8 输出按 replace 解码，不再 traceback、也不丢回执。
- `overlay cover`：trace 里 `relates` 不是列表时报契约错误（退出 2），不再 TypeError。
- `overlay generate`：只有 `OPENROUTER_API_KEY` 时默认发往 OpenRouter，不把它的 key 发给 api.openai.com；URL 无 scheme、HTTP 4xx/5xx、`IncompleteRead` 都一行报错退出 2；叶子文本里出现 `#` 标题或代码围栏则拒写；`suite.yaml` 解析不了时 `--force` 也拒绝（不能证明不是 `blocked`）；目录里只有 `cases.md` 也算已存在，需要 `--force`。
- `overlay migrate`：`blocked_reason` 没有链接或登记号时与 validate 同标准，留作待办不改写；`never_red_statuses` 里带引号的 `- "draft"` 也会删除。
- `overlay validate`：同一 `cases.md` 里重复的 `## <function_id>` 报错。
- 文档：`use-overlay` 与 `overlay-select` 用例里「未知分支回落并保持绿」改为与 design §4.6 一致（无 `branches.default` 时退出 2）。
- `overlay select` / `run` 写回执时用解析后的分支名（省略 `--branch`：`GITHUB_BASE_REF`，否则已配置的 ref，否则 `branches.default`，再否则 `main`）。文件名不再收到 `None`。
- live `forge promote` 在 `agent_branch_prefixes`（`cursor/`、`copilot/`、`agent/`）上拒绝；`--dry-run` 仍可。人 / ops 分支不变。
- 工作本 `forge check` 跑与 CI 相同的 `python -m unittest discover -s tests -t .`。没有 `overlay/__init__.py` 的根不跑这套单测。
- `scripts/gen_cli_docs.py --check` 按词比对。CPython 3.13 的 argparse 换行与 3.12 不同，原先在 3.13 上 `unittest`（及工作本 `forge check`）假红。
- `ci-select`：产品门在标题选中 **或** 路径命中时跑。标题 `docs` 不再挡住碰到 `forge/` / `overlay/` 的 diff。未声明检查名仍 skip-success。
- 显式 `select --branch` / `run --branch` 的名字不在 `overlay.yaml` 且没有 `branches.default` 时退出 2。已配置分支选出 0 个套件仍退出 0。省略 `--branch` 时，PR 用 base ref；push 到已配置分支用该名；否则 `branches.default`，再否则仅当 ref 未配置时用 `main`。
- 工作本 Overlay CI 不再写死 `branch: main`。`overlay.yaml` 的 `dev` 与 `main` 同 kind。fixture job 仍传 `main`。
- `submit` 更新已有 PR 时按 **head 且 base** 匹配。同一功能枝上指向另一条保护分支的 open PR 不会被 PATCH。
- `promote` 标题在 `title.scopes` 允许时用 `chore(ci/agent):`，两扇产品门都跑。不再用列表第一项（工作本会变成只跑 Overlay），也不再使用过不了 `pr-title` 的 `release/agent`。`scopes: any` 同样用 `ci/agent`。见 [ADR 0003](docs/adr/0003-dev-main-promotion.md) 修订。
- `suite_guard`：agent 分支不得把已有 `blocked` 改回 `active` 或删掉。人枝仍只记录。
- Python 内核增加 ruff 门（`tests/style/test_ruff.py`，随 `unittest` 跑）。没有新的 GitHub job 名。
- Overlay `select` 断言文案不再把已删除的 `draft` 写成现行状态。
- `forge status` 的 drifted 比对整条规范化 payload：`enforcement`、`bypass_actors`、`ref_name.exclude`、`require_last_push_approval`、check 的 `integration_id` 都参与。被停用、加了 bypass 或 exclude 的 Ruleset 不再报 installed。check 顺序不再算漂移。
- live `apply` / `release` 的禁仓守卫总是同时查源码内置 `FORBIDDEN_REPOS`（大小写不敏感）。用目标仓自己的 `forge.yaml` 或不带 `--path` 时不再放行。
- `forbidden_live_repos` 条目规范化（去 `https://github.com/`、`github.com/`、`.git`、末尾 `/`，转小写）；仍不是 `OWNER/NAME` 的退出 3。
- `branches.<name>` 与 `review` 的未知键退出 3 并给 did-you-mean；`branches:` 里不在 `protect` 的分支、`promote_from` 指向不在 `protect` 的分支都退出 3。
- `sop-lock` 用解析后的 `forge.yaml` 判 required checks：每条保护分支都要含五个工作本检查名，`main` 要 `approvals ≥ 1` 且 `code_owners: true`。注释里出现名字不再算。
- `sop-lock` 用 PyYAML 锁 `ci.yml` 的 `pr-title` / `sop-lock` / `unittest`：拒绝 `continue-on-error`、`|| true`、`; exit 0`、`set +e`；`pr-title` 的 `if:` 必须正好是 `github.event_name == 'pull_request'`；另两个 job 不得有 `if:`。
- `sop-lock` 浮动 ref 锁：`uses:` 只接受 40 位 SHA 或版本 tag。`actions/checkout@main`、`@dev`、`@refs/heads/main`、无 ref 都红。
- `status --check-state` 比对完整「保护分支」行（approvals、code_owners、promote_from 也比）。
- `status --path` 不存在时退出 3；省略时读 `<root>/forge.yaml`，不读 cwd。
- `apply` / `status` 列 Ruleset 翻完 `Link: rel="next"` 所有页，带 `includes_parents=false`，只认 `source_type: Repository`。第 100 条之后的 Forge Ruleset 不再被重复 POST。
- `bounce` 已有带 `overlay-ops-bounce` 标记的评论时不再重复发。`ops-review` 只按评论作者 login 认 CodeRabbit / Copilot，人写到 bot 名字不算。
- `forge check` 看不到 base（没有 `origin/<protect[0]>` / 本地保护枝 / `origin/$GITHUB_BASE_REF`）时，`deny_paths`、agent 枝 `suite_guard`、`docs_sync` 表**红**，提示 fetch；不再只比工作区与 HEAD 后假绿。
- `forge check` diff 并入已提交改动（merge-base..HEAD）。暂存回退不能藏住要推送的提交。
- `suite_guard`：detached HEAD 且无 CI 分支变量时按 agent 枝处理。`run_check` 新增 `head_branch` 参数。
- `forge check` / `ci-select` 的路径列表用 `git -z`：非 ASCII 路径不再因 `core.quotePath` 转义漏过 `deny_paths` / `suite_guard` / 链接检查。
- `deny_paths` 与 `docs_sync.paths` 共用 gitignore 式匹配：`**/` 零或多层目录，`*` 不跨 `/`。`deny_paths` 支持 glob；普通前缀写法不变。见 [`docs/forge-config.md`](docs/forge-config.md)。
- `ci-select`：`--no-renames`（移出产品仍选中该产品）；相对 `--root`（monorepo 子目录）；算不出变更路径时有标题也全跑。
- `ci`、`ci.products.<name>`、`ci.select` 下的未知键退出 3（did-you-mean）；`forge check` 同样拦下。
- `forge.yaml` 同一映射重复键退出 3，不再后写覆盖。
- `pr-title` 读不了 `forge.yaml` 时退出 3，不再悄悄丢掉 `title.scopes`。
- 没有 git 可执行文件时，`check` 的 git 步骤红（退出 2），不再抛 traceback。
- `submit` 拒绝 `--head HEAD` 以及 `heads/`、`refs/`、`tags/` 开头的名字，推送改用显式 `<sha>:refs/heads/<head>`。`HEAD` / `heads/dev` 不会再被 git 解析到保护分支上。
- `submit` 只推本工作树检查过的内容：`--head` 与当前检出分支不同、或工作树脏（含未跟踪文件）时退出 3（`--dry-run` 同样拒绝）。check 前记下 HEAD sha，推的就是这个 sha。
- 再次 `submit` 更新已有 PR 时只 PATCH 标题，不再用空的六节模板覆盖作者写好的正文。
- `submit` 的 token 经 `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_n` / `GIT_CONFIG_VALUE_n` 环境变量交给 git，不再出现在 argv（`ps` 可见）。先写一条空的 `http.https://github.com/.extraheader` 清掉继承的 extraheader（如 actions/checkout 的 `GITHUB_TOKEN`），只发 `FORGE_SUBMIT_TOKEN`。
- `promote` 按 ADR 0003「没有 `promote_from` 就不走晋升」：目标分支没有 `promote_from`、或 `--from` 不在 `protect` 时退出 3。
- `promote` 与 `release` 一样拒绝 `forbidden_live_repos` 与源码硬拒的上游仓（大小写不敏感）。
- live `promote` 在解析不出当前分支（detached HEAD 且无 `GITHUB_HEAD_REF` / `GITHUB_REF_NAME`）时拒绝；`--dry-run` 仍可。
- `release` 总是核对每个所选产品的 `<product>/__init__.py` `__version__`，缺文件即红（不再只在有 `overlay/__init__.py` 时才查）。`--products both` 先检查全部 tag / Release，再发布，不会半发。
- 连 GitHub API 的命令拒绝非 https 的 `FORGE_GITHUB_API`（退出 3），token 不走 http。仅 `127.0.0.1` / `localhost` 测试服务允许 http。

### Changed

- 工作本 `forge-check` 选中时跑 `python3 -m forge check --root .`（`pull_request` 传 `PR_TITLE` / `PR_BODY`，`push` lint HEAD subject）；deny_paths / suite_guard / docs_sync 不再只在本机成立。原来的 `forge unit tests` 步骤去掉：`forge check` 已跑全量 `unittest discover -s tests -t .`。`sop-lock` 改为要求 `forge-check.yml` 跑 `forge check`。
- 分支 Ruleset 的 `required_status_checks` 带 `integration_id`，`pull_request` 多写 `allowed_merge_methods` / `required_review_thread_resolution`，`require_last_push_approval` 随 `approvals` 默认 true。**已装的 Ruleset 会被 `status` 报成 drifted，重新 `apply` 一次即可。**
- 保护分支 `required_checks` 为空时不再写一条空 contexts 的 `required_status_checks`，改为省略该规则并警告。
- 冷启动与 skill 的当前 Forge 针改为已发布的 `forge-v1.1.3`。`overlay-v2.0.0` peel 仍是 Forge 1.1.0（空根 `check` 假绿），必须第二针。不要用 GitHub Release Latest 当针。
- `apply` 必须 `--path` 指向目标仓自己的 `forge.yaml`。不要在工具仓根对产品仓 live apply。接入方最小例改指 `examples/acme-python/`。
- ADR 0007 仍是**提议**，未接受。

## [forge-1.1.3]

### Fixed

- PR 规格按**事件 × 来源**取值，不再把空白 `PR_TITLE` 当成「没有规格就 skip」。`1.1.2` 把 Actions 在 `push` 上写成的空串当成已提供标题并报 `empty PR title`；中间一刀「空白就 skip」是绕过，旧夹具（好 `--title` / `--title ""` / 缺 actor）没锁到 `GITHUB_EVENT_NAME`、`PR_TITLE` 空串、以及 `forge check` 在 push 上嵌 pr-title。
- 来源表：`--title` / `--body`（含显式空串）→ 按参数 lint；非空 `PR_TITLE` / `PR_BODY` → 按环境 lint；`pull_request` + 空白或未设标题/正文 → 空规格，红（正文在有 `docs/pr-brief.md` 时查六个标题）；`push` 或 Actions 空串（环境已设、不是 `pull_request`）→ lint HEAD 提交第一行（先 `GITHUB_EVENT_PATH` 的 `head_commit.message`，否则 `git log -1 --format=%s`）；本地无事件且环境未设 → 省略，`forge check` skip。
- 夹具：新叶子 `FN-forge-pr-title` + `INV-pr-spec-event-states`。`ci-select` 在 push 空 `PR_TITLE` 时用提交标题的产品面。
- 冷启动说明只 pin **已存在**的 tag（`overlay-v2.0.0` / `forge-v1.1.2`）。`use-forge` 收成开发六步；live apply 只在 `manage-repo`。仓顶 README / README.zh-CN 的 30 秒命令带 `git checkout`，不再默认落到浮动 `main`。不自动打下一针。
- `forge check` 在 `--root` 既无 `forge.yaml` 又无 `overlay.yaml` 时退出 2（「不是产品根；先 cd」），不再全 skip 后打印 `forge check: ok`。
- 冷启动一律 `python3 -m forge` / `python3 -m overlay`。`pip install -r requirements.txt` **不会** 装出 `forge` 命令，必须 `PYTHONPATH` + `python3 -m`。Overlay 针 `overlay-v2.0.0`，Forge CLI 针 `forge-v1.1.2`（发 1.1.3 后再改）。`1.1.2` 的 CI `push` 不要设空 `PR_TITLE`；`1.1.3` 后 push 锁提交 subject。

### Added

- 补设计：提交内容包按层配对（[ADR 0007](docs/adr/0007-content-package-layers.md)，提议）。一开始只有配对锁、没有包规格。人接受前不加新的 `docs_sync` / CLI / workflow。

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
