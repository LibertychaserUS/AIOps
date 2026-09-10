# 两件产品：怎么做、怎么复用

本仓是工作本，不是某一家业务仓。做出两件 **可安装到任意 GitHub 仓** 的产品。Learning Guide 是第一个接入方，不是产品本身。

| 产品 | 代号 | 一句话 |
|---|---|---|
| GitHub 协作规范 | **Forge** | 把多人 + agent 在 GitHub 上的开发变成只开 PR、有审、不直推保护分支 |
| 测例生成与 CI | **Overlay** | 需求 → 可审用例；push 只跑 `armed`；不替代接入方已有构建门 |

两件产品独立版本、独立接入、独立失败。Forge 不懂用例；Overlay 不管谁该 merge。接入方可以只装一件。

完整详细设计：[`design.md`](design.md)。Inbox：[`inbox.md`](inbox.md)。测试规格：[`test-spec.md`](test-spec.md)。过程稿：[`architecture.md`](architecture.md)。约束：[`2026-09-10-对话整理.md`](2026-09-10-对话整理.md)。

---

## 共同规矩

- 账本是 **接入方自己的 GitHub 仓**，不是本仓数据库，不是门户。
- 交付物是 **模板 + CPython CLI + reusable workflow**，不是 SaaS。
- 标准 CPython 3.12+。C 扩展只留给量过的热路径。
- 不做 CD。不打接入方生产域名。不改接入方已有构建 workflow（Learning Guide 的 Verify 是这一条的第一例）。
- 不 attach 任何仓的 Proctor / intern 监考。
- Agent 只开 PR，不直推保护分支，不自 merge，不写 Overlay 的 `reviewed_by` / 回执。

---

## 产品 A — Forge（协作规范）

### 要解决什么

人多了、再加会写代码的 agent，GitHub 上会直推 `main`、互踩、无人审就合。Forge 把「怎么写这个仓」变成 **同一套可重复安装的政策**，不自建协作网站。

### 做成什么（标准件）

装进任意 `owner/repo` 的一组文件 + 一条 GitHub API 调用：

| 标准件 | 作用 | 接入方要改的 |
|---|---|---|
| `forge/ruleset.protected-default.json` | 保护 `main`（及接入方列出的分支）：禁 force push、禁直推、必须 PR | 分支名 |
| `forge/CODEOWNERS.example` | 路径 → 必须审的人 | 团队 @名 |
| `forge/agent-policy.md` | 写进接入方 `AGENTS.md` / Copilot instructions：只开 PR、不碰 secrets、不改构建门 | 仓名 |
| `.github/workflows/forge-guard.yml` | reusable：校验 PR 来自允许的前缀、没有改保护 workflow | 分支前缀（默认 `cursor/`, `copilot/`） |
| `python -m forge apply --repo owner/name` | 用 GitHub API 安装 Ruleset（幂等） | token 权限 |

评审：继续用接入方已有的 **CodeRabbit**（或同等 PR review）。Forge 不重做 diff 审。Copilot review 只当建议，不当 merge 门。

写代码的 agent：接入方已有的 **Copilot coding agent** 或 **Cursor cloud agent**。Forge 不管它们怎么想，只管它们落地时必须过 Ruleset。

### 接入（任意项目）

```text
1. 在目标仓加 forge-guard workflow（uses: this-repo/.github/workflows/forge-guard.yml@vX）
2. 复制 CODEOWNERS、agent-policy 片段
3. forge apply --repo owner/name
4. 把「构建已绿」设为 required check（用接入方自己的 CI 名，不替他们写）
```

Learning Guide：Ruleset 加在产品仓 + 本工作本；**不改** `.github/workflows/ci.yml`。Agent 改产品代码只能开 PR。

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
| `schema/suite.schema.json` + `cases.md` | 接入方测试规格：三种状态 + `REQ-n`（追溯 inbox，不抄 PRD） | 无 |
| `python -m overlay generate` | 一篇 `inbox/<id>.md` → 一个 `suites/<id>/`，`status: draft`（才花 token；不改 inbox） | 提示词可覆写 |
| `python -m overlay select --branch` | 只输出该分支该跑的 `armed` | `overlay.yaml` 的 branches |
| `python -m overlay receipt` | 程序写回执，模型不写 | 无 |
| `.github/workflows/overlay.yml` | reusable：校验契约 + select 预演；后一刀按 `product_command` 跑 | checkout 哪个仓、跑哪条命令 |
| `overlay.yaml` | 产品仓 pin、分支、never_red | **整份都是接入方的** |

状态机、回执、和 Proctor 的语义对齐（没审过不跑、没证据不过）是 Overlay 的标准，不复制七段监考。

### 接入（任意项目）

```text
目标仓（或旁边一个 overlay 仓）里：
  inbox/                 该项目的需求摘录（一篇 inbox = 一个 suite；合同见 docs/inbox.md）
  suites/                该项目的测试规格（cases.md 正文；追溯 inbox，不抄 PRD 目录）
  overlay.yaml           指向该项目的代码仓与脚本
  uses: overlay.yml@vX
```

Learning Guide 只是一份 **fixture**：`examples/learning-guide/overlay.yaml` 指向 `LearningGuidePortal`，支付/登录默认 `blocked`，My Learning 可 `armed`。别的项目换 inbox 和 `product_command`，不改 Overlay 源码。

### 第一刀 / 以后

- 第一刀：契约 + `select` + 预演 workflow + 示例 inbox/suite（LG fixture 是三篇 inbox，不是一篇复用三次）。没有 generator 也能手写证明状态机。
- 以后：`generate` 稳定；checkout 接入方仓跑 `product_command`。不把用例自动灌进接入方构建门。

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

```text
forge/                  # 产品 A
  ruleset.protected-default.json
  CODEOWNERS.example
  agent-policy.md
  apply.py
overlay/                # 产品 B（或 src/overlay）
  generate.py
  select.py
  receipt.py
schema/                 # Overlay 契约，跨项目冻住
examples/learning-guide/   # 第一个接入方，不是核心
.github/workflows/
  forge-guard.yml
  overlay.yml
```

版本：`forge@v1`、`overlay@v1` 分开打 tag。接入方 pin tag，不 pin 本仓 `main`。
