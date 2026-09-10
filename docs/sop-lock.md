# SOP 程序锁

原则（一句）：**skill 写明的、能机器判定的标准，必须有对应程序检查。** **通用**检查（`pr-title` / `sop-lock`）≠ **产品门**（`overlay-check` / `forge-check`）。产品门由 `forge.yaml` 的 `ci` 选择器（`python -m forge ci-select`）决定跑不跑；通用检查总是跑。

两道锁，不要混：

| 锁 | 命令 | 挡住什么 |
|---|---|---|
| **代推锁（提交前）** | `python -m forge check` 绿，且持有 `FORGE_SUBMIT_TOKEN`（`submit` 先探测再跑 check） | 不绿或缺 `FORGE_SUBMIT_TOKEN`则 **不 push、不开 PR**（含 `--dry-run`） |
| **合入锁** | GitHub required checks / Ruleset | 不绿则 **不能合** |

GitHub required checks 锁的是 merge，不是 submit。本地 `python -m forge check` 才是开发侧代推门。

不声称用 NLP 锁住全部散文。只锁**可判定子集**。每个 skill 的 `## Lock` 指向程序。存货如下。

**通用检查 ≠ 产品门。** `pr-title` 与 `sop-lock` 是仓级通用检查（`forge.yaml` `ci.common`），始终跑。`overlay-check` 与 `forge-check` 是两件产品的产品门（`ci.products`）；workflow 必启动，跳过由 `python -m forge ci-select` 写成 success，不靠 `on.paths`。

本工作本 Ruleset 要勾的检查名（`forge.yaml` `required_checks`）：

| 检查名 | 类 | 命令 | 何时 |
|---|---|---|---|
| **`overlay-check`** | 产品门 + Overlay Ops 链 | PR 上：规格 `pr-title` → `ops-review`（CodeRabbit/Copilot，只建议）→ 本分支全量 Overlay CI（validate/select/run）；失败 `bounce` 打回并留 `ops-debug` | push 无 PR 面，直接全量 CI；selector 可 skip-success |
| **`forge-check`** | 产品门 | Forge 单测（`unittest discover -s tests/forge`）+ `forge apply --dry-run` | push / pull_request；selector 可 skip-success |
| **`pr-title`** | 通用 | `python -m forge pr-title`（Conventional Commits `type(product/actor): subject` + 正文六节） | 仅 `pull_request` |
| **`sop-lock`** | 通用 | `python -m forge sop-lock` | push / pull_request |

不要 live `forge apply`。不要 husky / npm 挡 `git commit`。不要另开 `self-test` 旁路绕过 Overlay select。Forge 单测走 **`forge-check` 产品门**，不是 Overlay run。`sop-lock` 是通用检查，不代替任一产品门。不要把 GitHub check 当成提交前检查。

两道锁：

| 何时 | 程序 | 红了怎样 |
|---|---|---|
| **代推**（push + 开 PR） | `python -m forge check` 绿，且持有非空 `FORGE_SUBMIT_TOKEN` | `forge submit` 拒绝，不 push、不开 PR |
| **合入**（merge） | GitHub required checks：通用 `pr-title` + `sop-lock`（永远跑）；产品 `overlay-check` + `forge-check`（选跑或 skip 成功） | Ruleset 挡 merge |

---

## 存货

| 规则（skill / SOP 已写明） | 锁定（命令 / 检查） | 仅人审 | 备注 |
|---|---|---|---|
| armed 叶子三技法 Functional / Negative / Edge | `overlay validate` / `cover` → **`overlay-check`** | — | `draft` / `blocked` 可薄 |
| 已声明 invariant 必须在某篇 `cases.md` 点名 | `overlay validate` / `cover` → **`overlay-check`** | 这条 invariant 该不该存在 | 不 NLP 扫 PRD |
| `blocked` / `draft` 永不入选、不把 check 染红 | `overlay select` / `run` → **`overlay-check`** | — | `INV-never-red-blocked` |
| 回执只能 `select` / `run` 写 | Overlay 源码 + 单测 → **`overlay-check`** | 模型有没有手改回执 | |
| `product_command` 不得打 `forbid_hosts` | `overlay run` → **`overlay-check`** | 人在本机 curl 生产 | |
| inbox 禁止 `status` / `reviewed_by` / `armed` | `overlay validate` → **`overlay-check`** | — | |
| `armed`/`blocked` 要 `reviewed_by` + 理由 | `overlay validate` → **`overlay-check`** | `reviewed_by` 是不是真人 | `overlay review` 本刀拒写盘 |
| 内核 `function_id` 不冻产品号段；schema 不写 LG 域名 | `schema/check.py`（`overlay-check` + `sop-lock`） | 接入方编号好不好 | |
| Overlay 内核 `.py` 不含 `ilovelearningguide` / `LearningGuidePortal` | `python -m forge sop-lock` → **`sop-lock`** | 文档里点名禁令 | fixture 在 `examples/` |
| push workflow 不跑 `overlay generate`、不设 `OPENAI_API_KEY` | `sop-lock` 扫 `.github/workflows` | dispatch / 人点 generate（未交付） | |
| 不 `workflow_call` 产品 `ci.yml` / Verify；不 checkout `LearningGuidePortal` | `sop-lock` | 改别的仓的 Verify | |
| reusable `uses:` 不钉浮动 `main`/`master`/`HEAD`/`latest` | `sop-lock` | 接入方仓是否 pin | 相对路径合法 |
| Overlay push 上不另开 `self-test` / 旁路 `unittest discover` | `sop-lock` | — | Overlay 单测进 Overlay armed `product_command`；Forge 单测进 **`forge-check`** |
| 本工作本 `forge.yaml` 列出 `overlay-check`、`pr-title`、`forge-check`、`sop-lock`；`apply` 写入 Ruleset `required_status_checks`；CodeRabbit 不能当唯一门 | `sop-lock` + `forge apply --dry-run` | 目标仓是否真跑过 apply | 不 live apply LearningGuidePortal |
| 每个 `skills/*/SKILL.md` 有 `## Lock` 并指向程序 | `sop-lock` | Lock 段落写得清不清 | |
| PR 标题 `type(product/actor): subject` | `python -m forge pr-title` → **`pr-title`** | 祈使句好不好读 | `[开发][Overlay]` 红 |
| 进 `main` 的 PR 必须封顶；squash 后换底；不从即将被压掉的旧头再叠 | `sop-lock` 扫 `pr-brief` / skill；`submit` base=`protect` | GitHub UI 是否把 PR base 指到另一条 `cursor/` 枝 | 提交内容规格化；默认 squash。不 NLP 验「这单够不够封顶」 |
| PR 正文六个 `##` 原样且按序 | 同上（`docs/pr-brief.md` 存在才锁） | 各节内容是否说清 | 不 NLP 验「不做什么」名单 |
| 代推前本地门必须绿 | `python -m forge check`（代推锁；`submit` 调用） | 人是否绕过 CLI 直 push | GitHub required checks 只锁合入；可选 `forge/hooks/pre-submit`，不装 husky |
| Live / dry-run `submit` 必须有`FORGE_SUBMIT_TOKEN` | `python -m forge submit` + `sop-lock` 扫源码 | 人是否直 `git push` | `gh auth login` / `GH_TOKEN` / 本机 extraheader / CI `GITHUB_TOKEN` 都不够。同一把 `FORGE_SUBMIT_TOKEN` 开 PR 并注入 HTTPS push。永不打印 token |
| LearningGuidePortal live `forge apply` 拒绝 | `python -m forge apply` + Forge 单测 → **`forge-check`**（产品门） | 人是否打别的仓 | |
| Forge 不写 Overlay `status` / `reviewed_by` | Forge 单测 → **`forge-check`**（产品门） | — | |
| 产品门按 `forge.yaml` `ci` 选跑或跳过 | `python -m forge ci-select` | 标题 product 写错 | 通用层不跳过 |
| 不装 husky / npm 当合入锁 | `sop-lock` | 开发本机自愿 hook | |
| Agent 不自 Approve / 不自 merge | — | **仅人审** | GitHub 人 + Ruleset |
| 开发不合自己让 agent 开的 PR | — | **仅人审** | |
| Overlay Ops：规格 → CodeRabbit/Copilot 评论 → 分支全量 CI → 人合 | `overlay-check.yml` job DAG + `python -m forge ops-review` / `bounce` → **`overlay-check`** | 人点 merge | 机器人评论不当合入门 |
| CI/合入失败：PR 打回；Ops/CI 留日志准备 debug | `python -m forge bounce` 写 `ops-debug.yaml` + artifact | 人是否真去看 artifact | 不合入 |
| 不 vendor 工具进产品仓 | — | **仅人审**（本仓 CI 看不见别的仓） | |
| 不 attach Proctor；不改 Deepseek3 | — | **仅人审** | |
| 不做 CD、不打生产（人手） | 命令命中 `forbid_hosts` 已锁 | 人在 runner 外打域名 | |
| 不自建管理端门户 / 第二套 RBAC | — | **仅人审** | |
| Agent 同一 PR 把 suite 标 `armed` | — | **仅人审**（易过拟合，不锁） | |
| 用例文案是否真测到角 | — | **仅人审** | `cover` 只看技法标题与 token |

---

## 本地

```text
python3 -m forge sop-lock --root .
python3 -m forge check --root . --title "feat(overlay/dev): add cover triad and invariants"
python3 -m forge pr-title --title "feat(overlay/dev): add cover triad and invariants"
python3 -m overlay validate --root .
python3 -m overlay cover --root .
```

`forge check` 在有 `overlay.yaml` 时跑 validate + cover；有 `--title` / `PR_TITLE` 时跑 `pr-title`；有 `docs/pr-brief.md` 且有 `--body` / `PR_BODY` 时 lint 正文；工具仓有 `schema/` 时跑 `schema/check.py`；本工作本有 `tests/` 时跑快单测子集；并跑 `sop-lock`。省略标题/正文会 skip，并写明 CI 会 lint `PR_TITLE` / `PR_BODY`——本地绿 ≠ CI 已过同一把锁。退出 2 则 `submit` 拒绝。可选：`forge/hooks/pre-submit`（opt-in，不默认安装）。
