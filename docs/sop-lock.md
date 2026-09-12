# SOP 程序锁

原则（一句）：**skill 写明的、能机器判定的标准，必须有对应程序检查。** **通用**检查（`pr-title` / `sop-lock`）≠ **产品门**（`overlay-check` / `forge-check`）。产品门由 `forge.yaml` 选择器（`python -m forge ci-select`）决定跑不跑；通用检查总是跑。工作本 `unittest` 永远跑，不走 ci-select。

两道锁，不要混：

| 锁 | 命令 | 挡住什么 |
|---|---|---|
| **代推锁（提交前）** | `python -m forge check` 绿，且持有 `FORGE_SUBMIT_TOKEN`（`submit` 先探测再跑 check） | 不绿或缺 `FORGE_SUBMIT_TOKEN`则 **不 push、不开 PR**（含 `--dry-run`） |
| **合入锁** | GitHub required checks / Ruleset | 不绿则 **不能合** |

GitHub required checks 锁的是 merge，不是 submit。本地 `python -m forge check` 才是开发侧代推门。

不声称用 NLP 锁住全部散文。只锁**可判定子集**。每个 skill 的 `## Lock` 指向程序。存货如下。

**通用检查 ≠ 产品门。** 文件归属是 **产品前缀分治**（[`ci-design.md`](ci-design.md)）：同前缀可合，跨产品不合。`pr-title` 与 `sop-lock` 是仓级通用检查，始终跑。`overlay-check` 与 `forge-check` 是两件产品的产品门；workflow 必启动，跳过由 `python -m forge ci-select` 写成 success，不靠 `on.paths`。本工作本把通用检查收进 `ci.yml`（jobs `pr-title` + `sop-lock`）；另 job `unittest` 永远跑。Forge 门是 `forge-check.yml`，Overlay 门 + Ops DAG 是 `overlay-check.yml`。不要把两件产品塞进同一个 workflow。接入方 pin reusable `overlay.yml`，不要拷本工作本 `ci.yml`。残留的 `pr-title.yml` / `sop-lock.yml` 会让 `sop-lock` 红。

本工作本 Ruleset 要勾的检查名见 [`STATE.md`](STATE.md) 与 `forge.yaml`。不要 live `forge apply`。不要 husky / npm 挡 `git commit`。不要另开旁路绕过 Overlay select。Forge 单测走 **`forge-check` 产品门** 或工作本 `unittest`，不是 Overlay run。`sop-lock` 是通用检查，不代替任一产品门。不要把 GitHub check 当成提交前检查。

两道锁：

| 何时 | 程序 | 红了怎样 |
|---|---|---|
| **代推**（push + 开 PR） | `python -m forge check` 绿，且持有非空 `FORGE_SUBMIT_TOKEN` | `forge submit` 拒绝，不 push、不开 PR |
| **合入**（merge） | GitHub required checks：通用 `pr-title` + `sop-lock`（永远跑）；工作本 `unittest`；产品门按分支 | Ruleset 挡 merge |

进保护分支必须 **squash 封顶**；合完 **换底**。

---

## 存货

| 规则（skill / SOP 已写明） | 锁定（命令 / 检查） | 仅人审 | 备注 |
|---|---|---|---|
| `active` 叶子三技法 Functional / Negative / Edge | `overlay validate` / `cover` → **`overlay-check`** | — | `blocked` 可薄 |
| 已声明 invariant 必须在某篇 `cases.md` 点名 | `overlay validate` / `cover` → **`overlay-check`** | 这条 invariant 该不该存在 | 不 NLP 扫 PRD |
| `blocked` 永不入选、不把 check 染红 | `overlay select` / `run` → **`overlay-check`** | — | `INV-never-red-blocked` |
| 回执只能 `select` / `run` 写 | Overlay 源码 + 单测 → **`overlay-check`** | 模型有没有手改回执 | |
| `product_command` 不得打 `forbid_hosts` | `overlay run` → **`overlay-check`** | 人在本机 curl 生产 | 字符串匹配，不是安全边界 |
| inbox 禁止 `status` / 审核字段 / `product_command` | `overlay validate` → **`overlay-check`** | — | |
| `blocked` 要带链接的 `blocked_reason` | `overlay validate` → **`overlay-check`** | reason 是不是真人写的 | |
| 内核 `function_id` 不冻产品号段；schema 不写产品域名 | `schema/check.py`（`overlay-check` + `sop-lock`） | 接入方编号好不好 | |
| Overlay 内核 `.py` 不含产品生产域名 / 产品仓路径 | `python -m forge sop-lock` → **`sop-lock`** | 文档里点名禁令 | fixture 在 `examples/` |
| push workflow 不跑 `overlay generate`、不设 `OPENAI_API_KEY` | `sop-lock` 扫 `.github/workflows` | dispatch / 人点 generate（未交付） | |
| 不 `workflow_call` 产品构建 workflow；不 checkout 外国产品仓 | `sop-lock` | 改别的仓的构建门 | |
| reusable `uses:` 不钉浮动 `main`/`master`/`HEAD`/`latest` | `sop-lock` | 接入方仓是否 pin | 相对路径合法 |
| Overlay push 上不另开旁路 `unittest discover` | `sop-lock` | — | Overlay 单测进 Overlay `product_command`；Forge 单测进 **`forge-check`**；`ci.yml` 的 `unittest` job 放行 |
| 本工作本 `forge.yaml` 列出产品门与通用检查；`apply` 写入 Ruleset；CodeRabbit 不能当唯一门 | `sop-lock` + `forge apply --dry-run` | 目标仓是否真跑过 apply | 不 live apply 禁仓 |
| 每个 `skills/*/SKILL.md` 有 `## Lock` 并指向程序 | `sop-lock` | Lock 段落写得清不清 | |
| PR 标题 Conventional Commits | `python -m forge pr-title` → **`pr-title`** | 祈使句好不好读 | `[开发][Overlay]` 红 |
| 进保护分支的 PR 必须封顶；squash 后换底；不从即将被压掉的旧头再叠 | `sop-lock` 扫 `pr-brief` / skill；`submit` base=`protect` | GitHub UI 是否把 PR base 指到另一条功能枝 | 提交内容规格化；默认 squash。不 NLP 验「这单够不够封顶」 |
| PR 正文六个 `##` 原样且按序 | 同上（`docs/pr-brief.md` 存在才锁） | 各节内容是否说清 | 不 NLP 验「不做什么」名单 |
| 代推前本地门必须绿 | `python -m forge check`（代推锁；`submit` 调用） | 人是否绕过 CLI 直 push | GitHub required checks 只锁合入 |
| Live / dry-run `submit` 必须有`FORGE_SUBMIT_TOKEN` | `python -m forge submit` + `sop-lock` 扫源码 | 人是否直 `git push` | `gh auth login` / `GH_TOKEN` / 本机 extraheader / CI `GITHUB_TOKEN` 都不够 |
| 禁仓 live `forge apply` 拒绝 | `python -m forge apply` + Forge 单测 → **`forge-check`** | 人是否打别的仓 | `forbidden_live_repos` |
| Forge 不写 Overlay `status` | Forge 单测 → **`forge-check`** | — | |
| 产品门按 `forge.yaml` 选跑或跳过 | `python -m forge ci-select` | 标题 product 写错 | 通用层不跳过 |
| 不装 husky / npm 当合入锁 | `sop-lock` | 开发本机自愿 hook | |
| Agent 不自 Approve / 不自 merge | — | **仅人审** | GitHub 人 + Ruleset |
| 开发不合自己让 agent 开的 PR | — | **仅人审** | |
| Overlay Ops：规格 → 评论机器人 → 分支全量 CI → 人合 | `overlay-check.yml` job DAG + `ops-review` / `bounce` → **`overlay-check`** | 人点 merge | 机器人评论不当合入门 |
| CI/合入失败：PR 打回；Ops/CI 留日志准备 debug | `python -m forge bounce` 写 `ops-debug.yaml` + artifact | 人是否真去看 artifact | 不合入 |
| 不 vendor 工具进产品仓 | — | **仅人审**（本仓 CI 看不见别的仓） | |
| 不 attach 监考进程 | — | **仅人审** | |
| 不做生产 CD、不打生产（人手） | 命令命中 `forbid_hosts` 已锁 | 人在 runner 外打域名 | 发布产品 tag ≠ 打生产；见 `docs/release.md` |
| 发新版本：两条 tag，仅 `workflow_dispatch` / `forge release` | `sop-lock` 扫 `release.yml` + `docs/release.md`；`python -m forge release --dry-run` | 人是否真点发布 | 不在 push 上自动发 |
| Codex/Cursor/Claude Code 能发现 `use-forge` / `use-overlay` | `sop-lock` 扫 `.agents/skills` `.cursor/skills` `.claude/skills` → `skills/` | 外来仓是否 `gh skill install` | 不 vendor 工具包 |
| 不自建管理端门户 / 第二套 RBAC | — | **仅人审** | |
| Agent 同一 PR 把套件标 `blocked` | `suite_guard` | 人枝只记录 | |
| 用例文案是否真测到角 | — | **仅人审** | `cover` 只看技法标题与 token |

---

## 本地

见 [`cli.md`](cli.md)。`forge check` 在有 `overlay.yaml` 时跑 validate + cover；pr-title / pr-body 按[事件 × 来源](forge-config.md#titlescopes)取值（`pull_request` 空白红，`push` lint 提交 subject，本地未设才 skip）；工具仓有 `schema/` 时跑 `schema/check.py`；并跑 `sop-lock`。退出 2 则 `submit` 拒绝。不要把空白 `PR_TITLE` 当成跳过标题锁。
