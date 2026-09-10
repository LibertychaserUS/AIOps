# AI CI Overlay — 架构、技术栈与系统设计

对照约束：[`2026-09-10-对话整理.md`](2026-09-10-对话整理.md)。  
本文件是下一刀实现的设计依据，不是实现说明。

仓：`LibertychaserUS/AIOps`（工作本）。不代替空仓 `First-Light-TechHK/AIOps`。不改产品仓 `First-Light-TechHK/LearningGuidePortal` 的 Verify。不做 CD。不按生产站 `ilovelearningguide.com`。

---

## 1. 先给结论

做成 **叠在 Git 上的薄层**（对话路线 A），不要做成产品门户、云 agent 舰队或独立测试平台。

系统只补现有 GitHub CI 不做的两件事：

1. **需求 → 可审用例**：PRD / user case（Figma 只当引用）进 inbox，AI 出 `draft`，人审成 `blocked` 或 `armed`。
2. **push 只跑已批准且已解禁的集**：配置分支上只执行 `armed`。`draft` / `blocked` 不跑、不当红。

Git 是唯一系统 of record。GitHub Actions 是执行器。CLI 是人机接口。没有数据库、没有 Web 工作台、没有部署。

第一刀成功标准（对话已拍板）：丢一篇已有 PRD（优先 My Learning）进去，当天有一页人审过的用例；支付 / 登录保持 `blocked`；已落地部分可以 `armed`；本仓 `main` 不因 `blocked` 变红。

---

## 2. 在现有地图上的位置

```text
产品仓 LearningGuidePortal
  Verify: Typecheck → Lint → Build and test     ← 不改、不替代
  另有 apprunner-deploy.yml                     ← 不碰、本仓不做 CD
  tests/{unit,integration,e2e} + Playwright
  docs/phase1/source-prd/*.docx                 ← 七份需求来源

实习工作区 Proctor / Deepseek3
  本机过程账本、gate、没证据不过               ← 不 attach、不改、不复做

本仓 AIOps
  inbox → generate → 人审 → suites
  Actions: 校验契约 + 只选 armed 来跑
```

产品仓已经能构建门禁。它缺的是「产品写的需求和开发推的代码对不齐」，以及「没做好的支付 / 登录测试被推进门就会必红」。CodeRabbit / GitLens 管 diff 评论，不管需求 → 用例。

Proctor 的规矩（没审过不跑、没证据不过）**只复用语义**，写成本仓的状态机和选择器。不复做七段生命周期，不写模型账本，不监考实习机。

---

## 3. 目标与非目标

### 做

| 做 | 不做成 |
|---|---|
| 人能读、能改的用例页 | 模型直接改产品代码 |
| 三种状态：`draft` / `blocked` / `armed` | 第四种状态、看板、角色后台 |
| 功能集 + 回归集 | 第一刀就上并发 / 压测 / 视觉 E2E |
| 测产品功能；agent 评测预留字段 | 第一刀就评 Tutor / Proctor |
| token 只在「点生成」时花 | 每次 push 调模型 |
| 失败挡开发（只挡 `armed` 红） | 为流程再加一层开发手续 |

### 明确不做

- 改 `LearningGuidePortal` 的 `.github/workflows/ci.yml`（Verify）。
- 在产品仓加「替代 Verify」的第二套构建门。
- attach / 运行 / 门禁实习工作区 Proctor。
- 编辑 Deepseek3。
- 对 `ilovelearningguide.com` 发请求或当测试环境。
- 搬 First-Light 空仓、搬整站开源测试平台。
- 覆盖率 agent、流量录制、自然语言 E2E 框架（对话表里第一刀标「不用」的那些）。

---

## 4. 架构

### 4.1 上下文

```text
产品经理                 开发
   │  inbox/*.md            │  push / PR comment「碰了谁的包」
   ▼                        ▼
┌─────────────────────────────────────────┐
│  LibertychaserUS/AIOps  (Git + Actions) │
│  生成（要 key） │ 选择（无模型） │ 执行  │
└───────────┬───────────────┬─────────────┘
            │ 只读 pin      │ 不改 Verify
            ▼               ▼
   LearningGuidePortal   本仓 Actions runner
   PRD / 代码 / 已有测试   （checkout 产品仓跑 armed）
```

人是审核器。模型只在生成器里出现一次。CI 是确定性程序。

### 4.2 容器（本仓内四件东西）

| 容器 | 职责 | 何时跑 | 是否花 token |
|---|---|---|---|
| **Inbox** | 需求原文或摘录 + 来源指针 | 人提交 | 否 |
| **Generator** | inbox → `suites/*/cases.md` + `suite.yaml`（`status: draft`） | 本地或 `workflow_dispatch` | 是 |
| **Registry** | 用例页 + 元数据；人改 yaml 完成审核 | git 提交 | 否 |
| **Selector / Runner** | 按分支选出 `armed`；校验契约；执行或预演 | push / PR | 否 |

生成和执行必须分开。push 路径上没有 LLM，避免踩踏、账单和不可复现的红灯。

### 4.3 状态机（三种，不许更多）

```text
        generate
inbox ──────────► draft
                    │
                    │ 人审（改 suite.yaml，禁止脚本「自动通过」）
                    ▼
              ┌─────────┬─────────┐
              │ blocked │  armed  │
              └─────────┴─────────┘
                 不跑         配置分支 push 才跑
                 不当红       红了修自己的 diff
```

| 状态 | 含义 | Selector |
|---|---|---|
| `draft` | AI 刚写，人没审 | 丢弃 |
| `blocked` | 人审过，功能没就绪（现：支付 / 登录） | 丢弃 |
| `armed` | 人审过，且对应代码声称可测 | 纳入该分支该跑的集 |

`blocked → armed` 也是人改字段，附一句就绪理由。没有「CI 自己升格」。

非法状态、缺字段、缺 `reviewed_by`：本仓契约校验红。这是 overlay 自己的质量门，不是产品功能红。

### 4.4 核心对象

**Inbox 条目**（`inbox/<id>.md`）

```yaml
---
id: my-learning
source:
  repo: First-Light-TechHK/LearningGuidePortal
  path: docs/phase1/source-prd/My_Learning_PRD_v1.0_0814.docx
  ref: <pin sha，禁止浮动 main>
kind: prd            # prd | user-case | figma-ref
packages: [modules/my-learning, app/[locale]/account]
---
# 人可读摘录或粘贴的 user case。不要把 2MB+ docx 拷进本仓。
```

**Suite**（`suites/<id>/`）

| 文件 | 角色 |
|---|---|
| `suite.yaml` | 机器读：状态、集种类、包、审核者 |
| `cases.md` | 人读：功能 / 负面 / 边界用例（先给人看） |
| `trace.yaml` | 可选：需求条 → 用例 id，便于看缺口 |

第一刀 `cases.md` 是用例，不是可执行 Playwright。可执行脚本是后一刀，且默认仍不进产品 Verify。

**Overlay 配置**（`config/overlay.yaml`）

```yaml
product:
  repo: First-Light-TechHK/LearningGuidePortal
  default_ref: <pin>
branches:
  main:
    run: [functional, regression]
  test:
    run: [functional, regression]
  hotfix:
    run: [functional]
kinds:
  concurrency: later      # 生产以后才有
  agent: later
never_red_statuses: [draft, blocked]
```

### 4.5 两条流水线

**A. 生成（人点，花钱）**

```text
inbox md
  → 抽需求条（提示词骨架借 ai-testcase-generation-engine）
  → 每条出 functional / negative / edge
  → 写成 cases.md；suite.yaml 固定 status=draft
  → 打开 PR，人改 status + reviewed_by
```

支付 / 登录相关 suite 人审后标 `blocked`，即使写得很完整。

**B. 选择 + 执行（push，不花钱）**

```text
读 config/overlay.yaml
  → 扫 suites/*/suite.yaml
  → 只留 status=armed 且 kind ∈ 该分支
  → 校验契约
  → 第一刀：打印将跑名单 + 断言 blocked/draft 不在名单（预演）
  → 后一刀：checkout 产品仓 pin，跑与 suite 声明对应的已有测试
```

「碰了谁的包」：PR / push comment 列出本次 diff 命中的 `packages`，减轻多人踩踏。这是路线 B 里唯一要并进 A 的部分。不做看 `main` 的云 agent。

### 4.6 和产品仓测试的衔接（不改 Verify）

产品仓现状（只读对齐，不改）：

- Verify：`node:22` + `npm ci` + `tsc` + lint + `npm run build` + `npm run test:ci`（unit + Playwright auth/integration）+ health。`test:e2e`、`smoke:product`、支付真卡不在 Actions。
- `test:payment` 独立 config；对话要求支付 / 登录可以生成用例，**不能**把必红集推进门禁。
- 七份 PRD 在 `docs/phase1/source-prd/`。实施地图：`docs/phase1/requirements-map.md`。
- 产品自己的完成定义已经要求每条用户路径有 service + API/页面测试。本仓补的是「需求对齐的可审集」和「按状态解禁」，不是再写一套构建。

衔接规则：

1. 本仓 Actions **不** `workflow_call` 进 Verify，也 **不** 在产品仓加并行构建 job。
2. 后一刀若要跑产品测试：本仓 checkout 产品仓，调用产品已有脚本（如 `test:unit` 过滤、或 suite 声明的 `product_command`）。失败记在本仓 check，产品 Verify 颜色不变。
3. 禁止把 `armed` 用例自动 PR 进产品 `tests/` 并挂上 Verify。人要带进产品仓，另开产品仓 PR，且仍不得改 `ci.yml`。
4. 本仓 runner 的 `baseURL` 只允许本地 / Actions 起的产品进程（产品 e2e 已是 `127.0.0.1:8080|3012`）。禁止指向生产域名。

### 4.7 Agent 测试（预留，第一刀不跑）

对话：我们是 AI Agent 系统，既测产品，也测 agent。

第一刀只产出产品功能用例。`suite.yaml` 可写 `subject: product | agent`，Selector 在 `kinds.agent: later` 时丢弃 `subject: agent`。Agent 集仍然走同一状态机。禁止用本仓去跑 Proctor 的 `eval` 或 intern workspace gate。

---

## 5. 技术栈选型

原则：工具先借再改；大部分能力 Actions 就能做；本仓极简，不和产品仓抢同一套构建。

**语言决定：本仓用标准 CPython 3.12+（自带字节码编译器）。源码写 Python。C 只留给量过的热路径，第一刀不写。**

CPython 能写 / 调 C：它自己就是 C 实现，官方 C API、`ctypes` / `cffi`、手写扩展模块都可以。这扇门开着。第一刀不走这扇门，不是因为「CPython 不能写 C」，是因为这层还没有 C 该加速的东西。

- **标准编译器** = CPython 自带的 `compile()` / `.pyc` 字节码编译，不是另装一个「Python 编译器」，也不是 Cython。
- 不用 TS：overlay 是「读 yaml / 写 md / 调一次 LLM / 选 armed」，不是 Next 应用。硬跟产品仓同形只会多一套 Node 工具链，换不来 Verify 兼容。
- 性能：生成被模型与网络卡住；选择是扫几十个 `suite.yaml`。墙钟时间不在解释器循环上。先写纯 Python；真有剖面数据再加 C 扩展。
- 不用 Cython 当主写法：和「用标准 CPython」重复，还多一套 `.pyx` 构建。以后若要 C，优先薄 C 模块 + CPython C API，而不是把仓库改成 Cython 工程。

产品仓继续是 TypeScript / Node 22。后一刀 checkout 产品仓跑 `product_command` 时，用产品自己的 Node，不把 Playwright 重写成 Python。

| 层 | 选用 | 理由 | 不用 |
|---|---|---|---|
| 语言 / 运行时 | **CPython 3.12+**（标准解释器 + 自带字节码编译） | 生成/选择都是 IO 与文本；和参考生成器同族；需要时再接 C | TypeScript 做 overlay；Cython 当主语言；第一刀就写 C 扩展 |
| 包管理 | **pip + `requirements.txt`（锁 `requirements.lock`）** | 第一刀依赖少 | npm、poetry/pdm 先不上 |
| 契约 | **YAML + pydantic v2** | 人改 yaml；启动时校验；参考仓已这样用 | Zod、数据库、JSON 配置后台 |
| 用例正文 | **Markdown** | 产品经理能审；GitHub 能看 | 第一刀就生成产品仓 `.spec.ts` 当门禁 |
| CLI | **`python -m aiops`**（`generate` / `select` / `review`） | 三个命令，无服务 | Streamlit、Next 工作台、tsx |
| LLM | **OpenAI 兼容 HTTP**（`OPENAI_BASE_URL` + key） | 产品已用 OpenRouter；可换供应商；temperature=0 | 绑死 Deepseek3；强制本机 Ollama；每次 push 调用 |
| CI | **本仓 GitHub Actions + `setup-python`** | 选择器是纯函数，无密钥也能预演 | 改产品 `ci.yml`；本仓再装 Node（除非后一刀跑产品命令） |
| 文档抽取 | 第一刀 **人手摘录 / 粘贴 md** | 七份 PRD 是大 docx，不进本仓 | 第一刀就上 Figma API + 视觉模型；不必为摘录上 Cython |
| 执行（后一刀） | 产品已有 **node:test + Playwright**（本仓只负责选出要跑的命令） | 不新发明 runner | Midscene、Shortest、Keploy、cover-agent |

### 参考项目怎么借

| 项目 | 借 | 不借 |
|---|---|---|
| [ai-testcase-generation-engine](https://github.com/rohitpkumar/ai-testcase-generation-engine) | 「抽需求 → 三类用例 → 对需求条」提示词骨架；`temperature=0`；pydantic 结构 | CSV/pandas 主路径、整站照搬 |
| [figma-playwright-gen-ai](https://github.com/meeviefranc/figma-playwright-gen-ai) | `cases.md` 的标题 / 步骤 / 期望格式 | Streamlit、Ollama、第一刀 Figma API、直接出 TS 脚本 |
| cover-agent / ai-test-generator / midscene / shortest / keploy | — | 第一刀全部不用 |

### 平衡四件事（选型怎么兑现）

| 维度 | 做法 |
|---|---|
| 可用性 | 用例是 md，审选用改一行 yaml；当天能产出一页 |
| 大家少干闲活 | 开发只修 `armed` 红的 diff；不注册、不填工单、不编译扩展 |
| token | 只 `generate` 花；push 零模型；inbox 用摘录不是整本 docx |
| 开发速度 | 无服务、无库表、无 TS 工具链、无第一刀 C/Cython 构建；契约用示例 yaml 即可开工 |

---

## 6. 本仓布局（实现时按此长，现在不必一次建齐）

```text
inbox/                      # 产品录入
suites/<id>/suite.yaml      # 状态与选择键
suites/<id>/cases.md        # 人审页
prompts/extract.md          # 借来的骨架，我们改
prompts/generate-cases.md
schema/suite.schema.json    # 契约（示例见 schema/suite.example.yaml）
config/overlay.yaml
src/aiops/generate.py
src/aiops/select.py         # 纯函数：branch → armed ids
src/aiops/review.py         # 只帮改字段，不自动通过
.github/workflows/overlay.yml
docs/2026-09-10-对话整理.md
docs/architecture.md        # 本文件
```

第一刀最低可运行集：`inbox` 一篇 + `suites` 一篇审过的 + `select` + Actions 预演。没有 generator 也能先手写一页证明状态机；有 generator 再把「当天产出」自动化。

---

## 7. 安全与密钥

- 生成器用仓库 Secret / 本地 `.env`。不提交 key。不把 PRD 全文打进公开 Actions 日志。
- Runner 不持有生产 Stripe / SES / 生产 `DATABASE_URL`。预演 job 零密钥。
- 后一刀若 checkout 产品仓：用公开代码 + 产品 e2e 已有的本地假密钥模式（`PAYMENT_MODE=demo` 或 e2e 自己的 session secret）。仍不打生产。

---

## 8. 第一刀 / 第二刀

**第一刀（对照对话成功标准）**

1. 契约：`suite.yaml` 字段冻住；非法即红。
2. Inbox：My Learning 摘录（指针指向产品仓 pin + 短 md）。
3. 生成或手写一页 `cases.md`，人审。
4. 支付 / 登录 suite：`blocked`。My Learning 已合且可测的切片：`armed`。
5. `select main` 不含 `blocked`/`draft`。本仓 push 不因此红。
6. PR comment 能列出 `packages`。

**第二刀（仍不做门户、不做舰队）**

1. Generator 稳定：一篇 inbox → 可复现 draft（temperature=0 + 提示词入仓）。
2. Runner：本仓 checkout 产品仓，只跑 suite 声明的产品命令。
3. 可选：inbox 里 Figma 链接当人审附件，仍不强制视觉 E2E。

再往后才考虑 `subject: agent`、并发集、把本设计回灌空仓 `First-Light-TechHK/AIOps`。

---

## 9. 实现时的验收清单

- [ ] 状态枚举只有三个；测试覆盖「选 main 时 blocked 不出现」。
- [ ] Generate 不在 `on: push` 里调用模型。
- [ ] 本仓任何 workflow 不修改、不 `workflow_call` 产品 Verify。
- [ ] 无对 `ilovelearningguide.com` 的 URL。
- [ ] 无 Proctor attach、无 Deepseek3 路径。
- [ ] 支付 / 登录 suite 在被标 `armed` 之前，main 预演保持绿。
- [ ] 丢 My Learning inbox 能得到一页人能审的用例。
