# 两件产品：怎么做、怎么复用

本仓是工作本，不是某一家业务仓。做出两件 **可接到任意 GitHub 仓** 的产品（产品仓只留薄配置，不 vendor 工具包）。Learning Guide 是第一个接入方，不是产品本身。

| 产品 | 代号 | 一句话 |
|---|---|---|
| GitHub 协作规范 | **Forge** | 开发侧代推开 PR（`submit`）；Ops 侧检查绿了人来合。不直推 protect，不合入 |
| 测例生成与 CI | **Overlay** | 需求 → 可审用例；push 只跑 `armed`；不替代接入方已有构建门 |

两件产品独立版本、独立接入、独立失败。Forge 不懂用例；Overlay 不管谁该 merge。接入方可以只装一件。

**通用检查 ≠ 产品门。** 不是两个产品各搞一套对等 CI。仓级规格（标题 Conventional Commits、正文六节、`sop-lock`）永远跑。产品门（`overlay-check` / `forge-check`）在 `forge.yaml` `ci` 里选择执行或跳过（workflow 必启动，skip 记成功）。`python -m forge ci-select`。不要把标题检查只挂在 Forge 下。

Overlay **Ops** Action CI（PR 且选中）顺序：规格 → CodeRabbit/Copilot 评论（只建议）→ 该 checkout 全量 Overlay CI → 人合。失败：PR 打回，Ops/CI 留 `ops-debug` / receipts。

完整详细设计：[`design.md`](design.md)。使用 skill（Codex `SKILL.md`）：[`sop.md`](sop.md)、[`../skills/use-forge/SKILL.md`](../skills/use-forge/SKILL.md)、[`../skills/use-overlay/SKILL.md`](../skills/use-overlay/SKILL.md)、[`../skills/design-cases/SKILL.md`](../skills/design-cases/SKILL.md)、管理端 [`../skills/manage-repo/SKILL.md`](../skills/manage-repo/SKILL.md)、开发端 [`../skills/dev-pr/SKILL.md`](../skills/dev-pr/SKILL.md)。Review / merge / RBAC：[`rbac.md`](rbac.md)。PR 解说规格：[`pr-brief.md`](pr-brief.md)。Inbox：[`inbox.md`](inbox.md)。测试规格：[`test-spec.md`](test-spec.md)。编译契约：[`agents/overlay-contract.md`](agents/overlay-contract.md)。IEEE 剖面：[`agents/ieee-test-system.md`](agents/ieee-test-system.md)。过程稿：[`architecture.md`](architecture.md)。约束：[`2026-09-10-对话整理.md`](2026-09-10-对话整理.md)。

---

## 复用：工具不进产品仓

**不要把工具（`forge/`、`overlay/`、`schema/`、`prompts/`、本工作本的 Python 包）上传到接入方要提交、推送的产品 Git 仓。** 工具留在 `LibertychaserUS/AIOps` 的本地 git，或接入方 **fork** 的本工作本。

产品仓只提交薄层：

| 产品仓提交 | 不提交 |
|---|---|
| `forge.yaml` / `overlay.yaml` | `forge/` 包、`overlay/` 包 |
| `inbox/` / `suites/` / 可选 `invariants.yaml` | `schema/`、`prompts/`（工具仓自带；接入方不必拷） |
| 一条薄 workflow：`uses:` 工具仓的 reusable workflow，pin **tag 或 SHA**，不要 `main` | 把本工作本整树 vendor / submodule 进产品仓 |

本地：工具仓或 fork 与产品仓并排放。`PYTHONPATH=<工具仓>` 再跑 `python3 -m forge` / `python3 -m overlay`。不要为了 import 把包 `git add` 进产品树。

CI：产品仓没有 `overlay/__init__.py` 时，reusable [`overlay.yml`](../.github/workflows/overlay.yml) 会 checkout `tool_repository`（默认 `LibertychaserUS/AIOps`）到 `_aiops` 并设 `PYTHONPATH`。这是正确复用路径。不要为了让 `local=true` 把 `overlay/` 拷进产品仓。

Fork 若已分叉、SHA 不在上游：`uses:` 指向该 fork 的 pin，并把 `tool_repository` / `tool_ref` 指到该 fork。永不 checkout LearningGuidePortal。

---

## 共同规矩

- 账本是 **接入方自己的 GitHub 仓**，不是本仓数据库，不是门户。账本文件是薄配置 + inbox/suites，不是工具源码。
- 交付物是 **模板 + CPython CLI + reusable workflow**，不是 SaaS。CLI 从本工作本或 fork 跑，不打进产品仓。
- 标准 CPython 3.12+。C 扩展只留给量过的热路径。
- 不做 CD。不打接入方生产域名。不改接入方已有构建 workflow（Learning Guide 的 Verify 是这一条的第一例）。
- 不 attach 任何仓的 Proctor / intern 监考。不改 Deepseek3。不对 `LearningGuidePortal` live apply。
- Agent 只开 PR，不直推保护分支，不自 merge，不写 Overlay 的 `reviewed_by` / 回执，不 `armed`。CI 不自动 armed。token 只在人点的 `generate`，不在 push。
- PR review / merge：**GitHub 上的人 + Ruleset**。没有管理端 Web，没有第二套权限库。见 [`rbac.md`](rbac.md)。

---

## 产品 A — Forge（协作规范）

### 要解决什么

人多了、再加会写代码的 agent，GitHub 上会直推 `main`、互踩、无人审就合。Forge 分两侧，不自建协作网站，也不做 Graphite 克隆 / 自动合入机器人：

- **开发侧**：先 `python -m forge check` 绿，且持有 `FORGE_SUBMIT_TOKEN`（代推锁），再 `python -m forge submit` 代推当前功能分支，开/更新 draft PR（对齐 [`gh pr create`](https://cli.github.com/manual/gh_pr_create)）。Forge 不保管密钥。check 红或无凭证（含 `--dry-run`）不 push。Ops merge 是另一套权限。
- **Ops 侧**：Ruleset required checks（合入锁）+ 人点 merge（对齐 [GitHub Ruleset required checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-status-checks-to-pass-before-merging)）。

完整分工：[`rbac.md`](rbac.md)、[`design.md`](design.md) §3。

### 做成什么（标准件）

标准件留在本工作本（或 fork）。接入方产品仓只加薄配置，再对目标 `owner/repo` 跑一条 GitHub API（从工具仓调用 `python -m forge`）：

| 标准件（在工具仓） | 作用 | 产品仓要改的 |
|---|---|---|
| `forge/ruleset.protected-default.json` | 保护 `main`（及接入方列出的分支）：禁 force push、禁直推、必须 PR | 分支名写在产品仓 `forge.yaml` |
| `forge/CODEOWNERS.example` | 路径 → 必须审的人 | 按需把**文本**贴进产品仓 `.github/CODEOWNERS`，不拷 `forge/` |
| `forge/agent-policy.md` | 写进接入方 `AGENTS.md` / Copilot instructions：只开 PR、不自 merge、不改构建门、不 arm | 贴文本，不 vendor 包 |
| `.github/workflows/forge-guard.yml` | reusable：校验 PR 来自允许的前缀、没有改保护 workflow | 产品仓一条薄 `uses:`（pin tag/SHA） |
| `python -m forge apply --repo owner/name` | Ops：用 GitHub API 安装 Ruleset（幂等）。不合入 | 本机 `PYTHONPATH` 指向工具仓；admin token |
| `python -m forge check` | 开发侧提交前本地门 | 红则不 push；`submit` 先跑 |
| `python -m forge submit --repo owner/name` | 开发侧代推：check 绿且持有非空 `FORGE_SUBMIT_TOKEN`后 push 功能分支 + `gh pr create` | 标题过 `pr-title`；无凭证含 `--dry-run` 也红；CI `GITHUB_TOKEN` 不是代推 |

评审：继续用接入方已有的 **CodeRabbit**（或同等 PR review）。Forge 不重做 diff 审。Copilot review 只当建议，不当 merge 门。

写代码的 agent：接入方已有的 **Copilot coding agent** 或 **Cursor cloud agent**。Forge 不管它们怎么想，只管它们落地时必须过 Ruleset。

### 接入（任意项目）

```text
0. 工具留在 LibertychaserUS/AIOps 或你的 fork。不要 git add forge/ 进产品仓。
1. 产品仓只加 forge.yaml（从 forge.example.yaml 改 protect / deny_paths）
2. 按需把 CODEOWNERS、agent-policy 的文本贴进产品仓（不是拷 forge/ 目录）
3. 本地：PYTHONPATH=<工具仓> python3 -m forge apply --repo owner/name --dry-run
   人拿 admin token 再 apply。禁止对 LearningGuidePortal live apply。
4. （guard 落地后）产品仓加一条薄 workflow：
   uses: LibertychaserUS/AIOps/.github/workflows/forge-guard.yml@<tag-or-sha>
   不要 pin 浮动 main。
5. 把「构建已绿」设为 required check（用接入方自己的 CI 名，不替他们写）
```

Learning Guide：本工作本可放 fixture；**不改** 产品仓 `.github/workflows/ci.yml` / Verify，不从这里 checkout Portal，不 live apply。Agent 改产品代码只能开 PR。

### 第一刀 / 以后

- 第一刀：Ruleset JSON + agent-policy 模板 + `apply` 能对一个仓装上「禁直推 main」。guard workflow 可以后补。
- 以后：Merge Queue、组织级 Ruleset、多仓一次 `apply`。仍不做舰队调度器。

### 成功标准（与业务无关）

对任意仓跑 `forge apply` 后：普通人与 agent 不能直推保护分支；能开 PR；policy 文件在仓里可审。

---

## 产品 B — Overlay（测例生成 + CI）

### 要解决什么

产品写的需求和开发推的代码对不齐；没就绪的集推进门就会必红。Overlay 让任意仓：**先有人审过的用例，再按状态跑**。

### 做成什么（标准件）

| 标准件 | 作用 | 接入方要改的 |
|---|---|---|
| `schema/` 契约 | 冻字段与状态机，不冻产品编号 / PRD 树 / IEEE 文件名。叶子用接入方自选的 `function_id` | 接入方自己的 id 与目录形状 |
| `python -m overlay generate` | 读 inbox，编成契约合法的 `suites/<id>/`，`status: draft`。无写死 FR 表 | 提示词可覆写 |
| `python -m overlay select --branch` | 只输出该分支该跑的 `armed` | `overlay.yaml` 的 branches |
| `python -m overlay receipt` | 程序写回执，模型不写 | 无 |
| `.github/workflows/overlay.yml` | reusable：校验契约 + select + 在**产品仓** checkout 里跑 `product_command`；产品仓无 `overlay/` 时再 checkout 本工作本到 `_aiops` | 产品仓一条薄 `uses:`（pin tag/SHA）；不要把 `overlay/` 拷进产品仓；不要从本工作本 checkout 外国产品仓 |
| `overlay.yaml` | 产品仓 pin、分支、never_red | **整份都是接入方的**；只提交这份 yaml，不提交 Overlay 源码 |

状态机、回执、和 Proctor 的语义对齐（没审过不跑、没证据不过）是 Overlay 的标准，不复制七段监考。

### 接入（任意项目）

```text
工具仓（LibertychaserUS/AIOps 或你的 fork，不要推进产品仓）：
  overlay/ schema/ prompts/ .github/workflows/overlay.yml

产品仓只提交：
  inbox/                 该项目的需求摘录（一篇 inbox = 一个 suite；合同见 docs/inbox.md）
  suites/                该项目的测试树实例（cases.md 用 function_id；两棵树对齐叶子）
  overlay.yaml           指向该项目的代码仓与脚本
  invariants.yaml        可选
  .github/workflows/overlay-check.yml
      uses: LibertychaserUS/AIOps/.github/workflows/overlay.yml@<tag-or-sha>
      # 产品仓自己的薄 caller，不是本工作本的 overlay-check.yml / ci.yml

本地：
  PYTHONPATH=<工具仓> python3 -m overlay validate --root <产品仓>
```

Learning Guide 只是一份 **fixture**：`examples/learning-guide/overlay.yaml` 指向 `LearningGuidePortal`，支付/登录默认 `blocked`，My Learning 可 `armed`。别的项目换 inbox 和 `product_command`，不改 Overlay 源码，也不要把 Overlay 源码打进那个产品仓。不 checkout Portal，不 live forge apply。

### 第一刀 / 以后

- 已做：契约 + `select` + `run` + `cover`（叶子三技法 + 声明的 invariant）+ 示例 inbox/suite（LG fixture 是三篇 inbox，不是一篇复用三次）。测试和 CI 同一条门。没有 generator 也能手写证明状态机。
- 以后：`generate` 稳定。不把用例自动灌进接入方构建门。不从本工作本 checkout LearningGuidePortal。

### 成功标准（与业务无关）

丢一篇该项目的需求进 inbox，当天有一页人审用例；`blocked` 不让该仓 overlay check 变红；`select` 可在无密钥的 Actions 里跑。

---

## 两件产品怎么接、怎么不接

```text
任意项目 GitHub 仓
    │
    ├─ 只装 Forge     → 开发有序，仍无需求对齐用例
    ├─ 只装 Overlay   → 有用例门，人仍可能直推 main
    └─ 两件都装（推荐）
         Forge Ruleset 可把 Overlay check 标成 required
         Overlay 红 = armed 集红，不是构建门红
         Agent（受 Forge 管）可以 dispatch Overlay generate
         Agent 不能 armed、不能写回执
```

禁止：

- Overlay 去改接入方构建 workflow。
- Forge 去改 `suite.yaml` 的 `status`。
- 一个二进制包死绑 Learning Guide 路由或生产域名。

---

## 本仓怎么长（实现时）

这是**工具工作本**（或它的 fork）的树，不是产品仓该拷的树。

```text
forge/                  # 产品 A — 留在本仓 / fork
  ruleset.protected-default.json
  CODEOWNERS.example
  agent-policy.md
  apply.py
overlay/                # 产品 B — 留在本仓 / fork
  validate.py
  select.py
  run.py
  receipt.py
schema/                 # Overlay 契约，跨项目冻住；不打进产品仓
examples/learning-guide/   # 第一个接入方 fixture，不是核心
.github/workflows/
  overlay.yml           # reusable；产品仓 uses: 本文件 @ pin（不要拷本工作本 ci.yml）
  overlay-check.yml     # Overlay 产品门 + Ops DAG（validate+select+run；ci-select 可 skip）
  forge-check.yml       # Forge 产品门（unit + apply --dry-run；ci-select 可 skip）
  ci.yml                # 本工作本通用检查：pr-title + sop-lock（检查名不变）
  release.yml           # 人点发布两条产品 tag；不是 CI
```

版本：两个产品两个 tag，不要看成一个 Latest。下一刀 pin `overlay-v1.0.1` / `forge-v1.0.1`（人在 `main` 上 `python -m forge release` 或 Actions `release` `workflow_dispatch`；见 [`release.md`](release.md)）。现在仍可 pin [`overlay-v1.0.0`](https://github.com/LibertychaserUS/AIOps/releases/tag/overlay-v1.0.0) 与 [`forge-v1.0.0`](https://github.com/LibertychaserUS/AIOps/releases/tag/forge-v1.0.0)。不 pin `main`。起步：仓库根 [`README.md`](../README.md)。
