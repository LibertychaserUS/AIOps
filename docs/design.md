# Forge + Overlay 完整设计

版本：0.1（设计冻结，供实现对照）  
工作本：`LibertychaserUS/AIOps`  
约束原文：[`2026-09-10-对话整理.md`](2026-09-10-对话整理.md)

本文是实现的单一对照。摘要见 [`products.md`](products.md)。Inbox 见 [`inbox.md`](inbox.md)。测试规格见 [`test-spec.md`](test-spec.md)。Agent 编译契约：[`agents/overlay-contract.md`](agents/overlay-contract.md)。IEEE 剖面：[`agents/ieee-test-system.md`](agents/ieee-test-system.md)。对话过程稿见 [`architecture.md`](architecture.md)。

Overlay 冻**字段与对齐方式**，不冻某产品的编号、PRD 树或 IEEE 文件名。接入方文档说了什么 id，人/agent 读完编进契约即可。两棵树用同一个接入方自选的 `function_id` 对齐。

---

## 0. 一句话

做出 **两件可安装到任意 GitHub 仓的产品**，不做成某一家业务的插件，不做成门户，不做成云 agent 舰队。

| 产品 | 代号 | 解决什么 |
|---|---|---|
| GitHub 协作规范 | **Forge** | 人 + agent 在 GitHub 上写同一仓时：只开 PR、有人审、不直推保护分支 |
| 测例生成与 CI | **Overlay** | 需求变成可审用例；push 只跑已批准且已解禁的集 |

Learning Guide / `LearningGuidePortal` 是 **第一个接入方（fixture）**，不是产品内核。接入方已有构建门（LG 上叫 Verify）不改、不替代。只做 CI，不做 CD。

---

## 1. 问题、用户、非目标

### 1.1 问题

1. 多人（再加会开 PR 的 agent）直推 `main`、互踩、无人审就合。GitLens / CodeRabbit 能看历史和 diff，不管「这个仓允许怎么落地」。
2. 产品写的需求和开发推的代码对不齐。没就绪的集（支付、登录）推进门就会必红。现有构建 CI 不管「需求 → 可审用例」和「按状态解禁」。

### 1.2 用户（角色，不先做后台）

| 角色 | 用 Forge | 用 Overlay |
|---|---|---|
| 产品 | 开 PR 交 inbox | 往 `inbox/` 丢需求摘录；审 `cases.md` |
| 开发 | 只开 PR；红了修自己的 diff | 只修 `armed` 红的部分，不加手续 |
| 测试（可虚拟） | 审 PR | 把 `draft` 标成 `blocked` 或 `armed` |
| Agent（Copilot coding / Cursor cloud） | 只开草稿 PR | 可被派去 `generate`（人点）；不能写 `reviewed_by` / 不能 `armed` |
| 接入方管理员 | `forge apply` | 写 `overlay.yaml`，挂 reusable workflow |

### 1.3 非目标（冻结）

- SaaS、数据库、Web 工作台、自建协作编辑器。
- CD、部署、打接入方生产域名（LG：`ilovelearningguide.com`）。
- 改接入方已有构建 workflow（LG：`.github/workflows/ci.yml` / Verify）。
- attach / 运行 / 门禁任何仓的 Proctor；编辑 Deepseek3。
- 覆盖率 agent、Midscene、Shortest、Keploy、流量录制。
- 第一刀：并发/压测、视觉 E2E、agent 评测、Figma API。
- Forge 改 Overlay 的 `status`；Overlay 改接入方构建 YAML。
- 模型写回执或 `reviewed_by`；CI 自动 `draft → armed`。
- 把两件产品焊成一只「万能云 agent」。

### 1.4 平衡

| 维 | 做法 |
|---|---|
| 可用 | 当天能审一页用例；`forge apply` 当天能挡住直推 |
| 少闲活 | 开发不注册、不填工单；审选用改一行 yaml |
| token | 只 `overlay generate` 花；push 零模型 |
| 速度 | 无服务、无 TS 工具链、无第一刀 C 扩展 |

---

## 2. 总架构

```text
                    任意 GitHub 仓（接入方）
                    ┌─────────────────────┐
     人 / agent ──► │  Forge（政策+Ruleset）│  只开 PR
                    └──────────┬──────────┘
                               │ 可选：Ruleset required check = Overlay
                               ▼
                    ┌─────────────────────┐
     inbox / PRD ─► │ Overlay（用例+选择） │  只跑 armed
                    └──────────┬──────────┘
                               │ checkout pin + product_command（后一刀）
                               ▼
                         接入方代码与已有测试
                         （不改其构建 workflow）
```

账本：接入方 Git。本工作本只发布 **模板、CLI、reusable workflow、JSON Schema**。  
运行时：GitHub Actions + 标准 CPython 3.12+。  
两件产品独立版本（`forge@v1` / `overlay@v1`），可只装一件。

和 Proctor：只复用「没审过不跑、没证据不过」。不复制七段生命周期，不跑它的 `eval`。回执由 Overlay 程序写；实习机可单向拷贝，Proctor 不得写 `suite.yaml`。

---

## 3. 产品 A — Forge

### 3.1 范围

Forge 把「这个仓怎么被写」装成可重复的政策。不管用例，不审 diff 内容（diff 仍交给 CodeRabbit + 人），不调度 agent 舰队。

### 3.2 对象

| 对象 | 存哪 | 说明 |
|---|---|---|
| Ruleset 文档 | `forge/ruleset.protected-default.json` | 安装到接入方 repo 的 GitHub Ruleset |
| 保护分支列表 | 接入方 `forge.yaml` → `protect` | 默认 `["main"]` |
| Agent 分支前缀 | `forge.yaml` → `agent_branch_prefixes` | 默认 `cursor/`, `copilot/` |
| 禁止 agent 改的路径 | `forge.yaml` → `deny_paths` | 默认接入方构建 workflow |
| CODEOWNERS | 接入方 `.github/CODEOWNERS` | 从 example 改团队名 |
| Agent 政策 | 接入方 `AGENTS.md` 或 `.github/copilot-instructions.md` | 粘贴 `forge/agent-policy.md` |
| Guard 结果 | Actions check `forge-guard` | 程序，无模型 |

接入方配置 `forge.yaml`（本工作本提供 example）：

```yaml
schema: forge-config/v1
protect:
  - main
agent_branch_prefixes:
  - cursor/
  - copilot/
deny_paths:
  - .github/workflows/ci.yml          # 接入方构建门；LG = Verify
required_checks:                      # 只声明名字，Forge 不创建这些 job
  - Verify                            # 接入方自己的
  # - overlay                         # 若同时装 Overlay，管理员在 Ruleset 里勾
review:
  min_approvals: 1
  code_owners: false                  # 第一刀默认关；有 CODEOWNERS 再开
```

### 3.3 Ruleset 行为（安装后由 GitHub 执行）

对 `protect` 中每个分支：

| 规则 | 值 |
|---|---|
| 删除分支 | 禁止 |
| 非快进 | 禁止（禁 force push） |
| 直推 | 禁止，必须 PR |
| 批准数 | `review.min_approvals`（默认 1） |
| 新推作废旧审 | 开 |
| CODEOWNERS 必审 | `review.code_owners` |
| bypass | 空。管理员若要 bypass，在 GitHub UI 加，不写进默认模板 |

Merge Queue：第一刀不装。人多了由接入方在同一 Ruleset 上打开，Forge 后一刀可加开关，默认关。

### 3.4 CLI

```text
python -m forge apply  --repo OWNER/NAME [--path forge.yaml] [--dry-run]
python -m forge status --repo OWNER/NAME
python -m forge revoke --repo OWNER/NAME --name forge-protected-default
```

`apply`：

1. 读 `forge.yaml`（缺省则用默认 protect=`main`）。
2. `GET` 该仓已有 Rulesets；若存在同名 `forge-protected-default` 则 `PUT`，否则 `POST`。幂等。
3. 不创建 CODEOWNERS / AGENTS.md（只打印「请复制这些文件」）。避免覆盖接入方已有政策。
4. 不修改任何 workflow YAML。
5. 成功打印 Ruleset id 与保护分支。失败非 0。

认证：`FORGE_GITHUB_TOKEN` 或 `GITHUB_TOKEN`。需要 `Administration: write`（Rulesets）。缺 token：退出码 `2`，不部分写入。

`status`：只读，列出是否已装、保护哪些分支。

### 3.5 Guard workflow（第一刀可后补，契约先冻）

Reusable：`LibertychaserUS/AIOps/.github/workflows/forge-guard.yml@forge-v1`。

触发：接入方 `pull_request`。

步骤（纯程序）：

1. 读 `forge.yaml`。
2. 若 head 分支匹配 `agent_branch_prefixes`：允许。人的分支也允许（第一刀不限制人的前缀，避免闲活）。
3. 若 PR 改动了 `deny_paths`：**失败**（agent 与人都不能从 PR 里改构建门；要改构建门必须管理员在 GitHub 改 Ruleset bypass 后另议——默认就是挡住）。
4. 不调用模型。不读 Overlay。

接入方：

```yaml
name: forge-guard
on: pull_request
jobs:
  guard:
    uses: LibertychaserUS/AIOps/.github/workflows/forge-guard.yml@forge-v1
```

### 3.6 Agent 政策（规范，GitHub 不执行全文，Ruleset 执行落地）

原文：[`../forge/agent-policy.md`](../forge/agent-policy.md)。实现不得削弱这几条：

- 只开 PR，不推保护分支。
- 不自 merge、不自 Approve。
- 不改接入方构建 workflow。
- 不写 Overlay `reviewed_by` / 回执，不把 `status` 改为 `armed`。
- 不打生产 URL，不 deploy。
- 人要求时可以 `workflow_dispatch` Overlay `generate`。

### 3.7 和现有工具

| 工具 | Forge 的态度 |
|---|---|
| GitHub PR / blame / GitLens | 留下，不重做 |
| CodeRabbit | 留下；接入方可把它的 check 标 required |
| Copilot code review | 建议；**不能**当唯一 merge 门 |
| Copilot coding agent / Cursor cloud | 允许写代码，必须过 Ruleset |
| HackMD / 飞书 / Notion | 不是 Forge 的一部分 |

### 3.8 错误码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 2 | 缺 token / 权限不足 |
| 3 | `forge.yaml` 非法 |
| 4 | GitHub API 失败（网络或 4xx/5xx） |
| 5 | dry-run 完成（可选；或仍用 0 + 打印）——实现选 0 + `--dry-run` 字样 |

### 3.9 测试（Forge 自己的，不测接入方业务）

- `apply` 对假 API：无 Ruleset 则 POST，有则 PUT，第二次无 POST。
- 默认 JSON 保护 `main`，含 PR 规则，bypass 为空。
- `forge.yaml` 缺字段用默认；非法枚举失败。
- Guard：改 `deny_paths` 的 diff fixture 必须红；只改 `README` 必须绿。

### 3.10 接入步骤（任意仓）

1. 复制 `forge.yaml` example，改 `protect` / `deny_paths`。
2. 复制 `agent-policy.md` 进 `AGENTS.md`。
3. 按需复制 `CODEOWNERS.example`。
4. `python -m forge apply --repo owner/name`。
5. （可选）挂 `forge-guard.yml@forge-v1`。
6. 在 GitHub UI 把接入方**自己的**构建 check 标 required（Forge 不代写名字以外的 job）。

LG：`deny_paths` 含 `.github/workflows/ci.yml`。不改 Verify 内容。

### 3.11 成功标准

任意仓 `apply` 后：人与 agent 不能直推 `protect` 分支；能开 PR；政策文件在仓里可审。与是否安装 Overlay 无关。

---

## 4. 产品 B — Overlay

### 4.1 范围

Overlay 让任意仓：**先有人审过的用例页，再按三种状态决定跑不跑**。不替代构建门。第一刀产出给人看的用例，不是门禁用的 Playwright 源码。

### 4.2 目录（接入方仓内，或旁边一个 overlay 仓）

```text
inbox/<id>.md
suites/<id>/suite.yaml
suites/<id>/cases.md
suites/<id>/trace.yaml          # 可选
overlay.yaml
receipts/<run-id>.yaml          # 程序写，不提交密钥
prompts/                        # 可选覆写；缺省用产品自带
```

本工作本：`schema/` 冻契约；`examples/learning-guide/` 是 fixture。

### 4.3 状态机（三种，不许更多）

```text
generate（模型，仅此时）     人审（改 yaml，禁止自动通过）
inbox ────────────────► draft ──────────────┬──► blocked
                                            └──► armed
```

| status | 含义 | select | 使 Overlay check 红？ |
|---|---|---|---|
| `draft` | 未审 | 丢弃 | 否 |
| `blocked` | 已审，功能未就绪 | 丢弃 | 否 |
| `armed` | 已审，且声称可测 | 纳入该分支 kind | **跑失败才红** |

合法转移：

| 从 | 到 | 谁 | 必填 |
|---|---|---|---|
| （无） | `draft` | `generate` 或人手写 | — |
| `draft` | `blocked` | 人 | `reviewed_by`, `blocked_reason` |
| `draft` | `armed` | 人 | `reviewed_by`, `armed_reason` |
| `blocked` | `armed` | 人 | `armed_reason`（可保留 `blocked_reason` 作历史） |
| `armed` | `blocked` | 人 | `blocked_reason` |
| 任何 | `draft` | 人（重生成后） | 清 `reviewed_by` |

禁止：CI、模型、Forge、Proctor 把状态写成 `armed`。  
`review` CLI 只改人指定的字段，默认不写 `reviewed_by`（必须 `--i-am HUMAN`）。

### 4.4 Inbox 契约

完整合同：[`docs/inbox.md`](inbox.md)。Front matter JSON Schema：[`schema/inbox.schema.json`](../schema/inbox.schema.json)。

一条 `inbox/<id>.md` 对应一次 `generate`、一个 `suites/<id>/`。Inbox 不是 case，不是闸门。`generate` 只读不改 inbox。人类改 inbox 走 PR。`select` / `run` 不读 inbox。

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `id` | string | 是 | `^[a-z0-9][a-z0-9-]*$`，最长 64，等于文件名（无扩展） |
| `kind` | enum | 是 | `prd` \| `user-case` \| `figma-ref` |
| `readiness` | enum | 否 | `ready` \| `not-ready` \| `unknown`。**提示**；generate 仍写 `status: draft` |
| `source` | object | 否 | 有则 `repo`+`path`+`ref` 都要 |
| `source.repo` | string | 随 source | `owner/name` |
| `source.path` | string | 随 source | 仓内相对路径，不 `..` |
| `source.ref` | string | 随 source | **禁止** `main`/`master`/`HEAD`/`latest`；应 pin commit 或 tag |
| `packages` | string[] | 否 | generate 原样写入 suite；第一刀可空 |
| `locale` | string | 否 | 提示词语言，默认 `en-GB` |
| 正文 | markdown | 是 | 摘录或 user case；禁止提交巨型二进制 PRD |

禁止出现在 inbox 上：`status`、`reviewed_by`、`armed`、`blocked`、`product_command`。  
`figma-ref`：只许 URL，第一刀不当输入给视觉模型。  
In scope **可以**在行首带接入方自选的 `function_id`（非空、无空白）；不是必须，也不是某号段正则。文档已有则抄，没有则铸。  
一对多第一刀不做：三篇切片 = 三篇 inbox，三个 suite。

### 4.5 Suite 契约

`suites/<id>/suite.yaml`（JSON Schema：实现时 `schema/suite.schema.json`，字段以本节为准）：

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | string | 等于目录名 |
| `title` | string | 非空 |
| `status` | enum | 仅 `draft`\|`blocked`\|`armed` |
| `kind` | enum | `functional`\|`regression` |
| `subject` | enum | `product`\|`agent`；第一刀 `agent` 一律被 select 丢弃 |
| `source` | string | 指向 `inbox/<id>.md` |
| `packages` | string[] | 可空 |
| `reviewed_by` | string\|null | `blocked`/`armed` 必填非空 |
| `reviewed_at` | string\|null | ISO-8601；有 `reviewed_by` 则必填 |
| `blocked_reason` | string\|null | `blocked` 必填 |
| `armed_reason` | string\|null | `armed` 必填 |
| `product_command` | string\|null | `run` 要执行的命令；缺省则 `skipped_no_command`，不红 |

`cases.md` 就是接入方**测试规格正文**（完整合同：[`docs/test-spec.md`](test-spec.md)；编译：[`docs/agents/overlay-contract.md`](agents/overlay-contract.md)；IEEE 剖面：[`docs/agents/ieee-test-system.md`](agents/ieee-test-system.md)）。产品文档树与测试树不是同一形状；用同一个接入方自选的 `function_id` 对齐。生成器必须吐这个骨架，人可改：

```markdown
# <title>

## FN-login-retry <一句话功能>

### Functional
- 标题
- 步骤
- 期望

### Negative
…

### Edge
…
```

`function_id` 契约：非空、仓内作为叶子身份唯一、稳定、无空白。接入方选字符串——文档已有则抄，没有则铸（内核例子用 `FN-login-retry`）。schema **不**把 `REQ-n`、FR 号段正则或 `LOGIN-01` 写成法律。层次是同一 id 的面。技法落在 `type`。测试规格**追溯**文档切片，**不抄** PRD 章节树。

`trace.yaml`（可选，schema：[`schema/trace.schema.json`](../schema/trace.schema.json)）：`{ function_id, case_id, type, level? }`。第一刀有则校验，无则不红。`level` 可缺。`armed` 至少一条 `## <function_id>`。回执事件应带 `function_id`，失败才能指回那片叶子。

非法 yaml / 缺必填 / 第四种 status：`overlay validate` 非 0。这是 Overlay **契约红**，不是业务功能红。

### 4.6 overlay.yaml（整份属于接入方）

```yaml
schema: overlay-config/v1
product:
  repo: owner/name
  default_ref: <pin>          # 禁止浮动 main
branches:
  main: { run: [functional, regression] }
  test: { run: [functional, regression] }
  hotfix: { run: [functional] }
kinds:
  concurrency: later          # later → select 永不选这类
  agent: later
never_red_statuses: [draft, blocked]
forbid_hosts:                 # runner 拒绝；接入方列自己的生产域
  - prod.example.com
```

分支不在表里：select 输出空集，预演绿（没东西跑 ≠ 失败）。

### 4.7 CLI

```text
python -m overlay validate [--root .]
python -m overlay generate --inbox inbox/<id>.md [--out suites/<id>]
python -m overlay select   --branch NAME [--root .] [--write-receipt receipts/]
python -m overlay review   --suite ID --status blocked|armed --i-am HUMAN --reason TEXT
python -m overlay run      --branch NAME [--root .] [--write-receipt DIR] [--workdir DIR]
python -m overlay cover    [--root .]
```

退出码：`0` 成功；`2` 契约/配置非法或 run 无回执 / 命中 forbid_hosts；`3` 缺 LLM 密钥（仅 generate）；`4` select 预演断言失败（例如 armed 集合里混进 blocked——那是实现 bug）；`5` run 中 armed 命令失败。

`validate`：扫全部 inbox + suite，不调模型。  
`select`：纯函数，无网络（除写文件）。  
`run`：select 之后执行 `product_command`；必须 `--write-receipt`。  
`cover`：打印 `function_id` 技法矩阵与 invariant 点名；契约问题同 validate。  
`generate`：唯一允许出站到 LLM 的命令（未交付）。

### 4.8 generate（算法）

输入：一篇 inbox。输出：`suites/<id>/cases.md` + `suite.yaml` 且 **`status` 必须为 `draft`**，`reviewed_by` 必须为 null。若目标已是 `armed`/`blocked`：拒绝覆盖，除非 `--force-draft`（仍变成 draft 并清空审核字段）。

步骤：

1. `validate` 该 inbox。
2. 拼提示词：产品自带 `prompts/extract.md` + `prompts/generate-cases.md`，接入方可在自己仓覆写同名文件。
3. 调 OpenAI 兼容 HTTP：`OPENAI_BASE_URL` + `OPENAI_API_KEY`（或 `OPENROUTER_API_KEY`）。`temperature=0`。超时 60s。
4. 解析模型 JSON（`function_id` + 三类技法用例）。必须抄 inbox In scope 行首的 id，不得改写成 `REQ-n`。失败则非 0，不写半套文件。内核没有写死的某产品 FR 清单。
5. 渲染 `cases.md`（二级标题为 `function_id`）。写 `suite.yaml`：`status=draft`，`kind=functional`，`subject=product`，`source` 指向 inbox。
6. 不打开 PR（Forge 管怎么落地）。调用方可随后自己开 PR。

参考：[ai-testcase-generation-engine](https://github.com/rohitpkumar/ai-testcase-generation-engine) 的「抽需求 → 功能/负面/边界」。不借 CSV/pandas 主路径。用例页格式参考 figma-playwright-gen-ai 的标题/步骤/期望，不借 Streamlit/Ollama。

禁止：`on: push` 的 workflow 里跑 `generate`。

### 4.9 select（算法，纯函数）

```
suites ← 读全部 suite.yaml
validate(suites, overlay.yaml)        # 失败则退出 2
for s in suites:
    if s.status in never_red_statuses: drop(s, rule=never_red_statuses)
    elif overlay.kinds[s.kind or s.subject] == later: drop(s, rule=kind_later)
    elif s.kind not in overlay.branches[branch].run: drop(s, rule=branch_kinds)
    elif s.status != armed: drop(s, rule=not_armed)   # 防御
    else: select(s)
assert no selected has status in {draft, blocked}     # 失败则退出 4
write receipt if --write-receipt
print selected ids
exit 0
```

CI：validate + select；`enable_run` 时在**调用方 checkout**里跑 `product_command`。不从本工作本 clone 外国产品仓。零密钥。`generate` 不在这条路上。

### 4.10 回执

`schema: overlay-receipt/v1`。字段见 [`../schema/receipt.example.yaml`](../schema/receipt.example.yaml)。

- `wrote_by` 仅 `select` | `run`。
- 事件：`selected` / `dropped` / `ran`（第二刀）/ `validated`。
- `evidence` 只引用盘上已有 `reviewed_by`，不新造审核者。
- 模型不得写此文件。实现里 receipt 模块不 import HTTP 客户端。

`ran`：每个执行了命令的 selected suite 一条，含 `exit_code` 与命令。无命令则 `skipped_no_command`。无回执的 `run` 视为没证据，退出 `2`。

### 4.11 reusable workflow

`LibertychaserUS/AIOps/.github/workflows/overlay.yml@overlay-v1`

```text
on: 由接入方映射 pull_request + push（及其分支）
jobs:
  validate:
    setup-python 3.12
    overlay validate
  select:
    needs: validate
    overlay select --branch ${{ github.ref_name 或 base_ref }} --write-receipt
    上传 receipt artifact
  run:
    needs: select
    若 enable_run：在调用方 checkout 对每个 selected 跑 product_command
    禁止请求 forbid_hosts；不 checkout 外国产品仓
```

接入方构建 workflow **不得** `workflow_call` 本文件。本文件也 **不得** `workflow_call` 接入方 Verify。

`enable_run` 默认 `false`。本工作本的 `overlay-check` 打开它，并把 `branch` 钉成 `main`，这样 agent 分支仍跑 armed 工具测试。

### 4.12 run（测试和 CI 同一条门）

- 工作目录：调用方当前 checkout（`--workdir`）。本工作本不 clone `product.repo`（避免误拉 LearningGuidePortal）。
- 命令：suite 的 `product_command`，缺省则跳过该 suite（记 receipt `skipped_no_command`，不红）。
- 环境：接入方已有的本地/CI 假密钥模式。禁止注入生产 Stripe/SES URL。
- 命令文本命中 `forbid_hosts` 的 URL → 退出 2，不启动该命令。
- 失败：仅 armed 命令非 0 使 job 红（退出 5）。无 `--write-receipt` → 退出 2。
- 本工作本：armed 的 `product_command` 就是 Forge/Overlay 的 unittest + dry-run。不要再开旁路 `self-test`。

禁止：自动把 `cases.md` PR 进接入方 `tests/` 并挂上构建门。

### 4.13 提示词（产品自带，接入方可覆写）

`prompts/extract.md`：只抽功能条 JSON：`[{function_id, text}]`。`function_id` 必须抄 inbox In scope 行首，不得改成 `REQ-n`。  
`prompts/generate-cases.md`：每条出 functional/negative/edge，字段 `title,steps[],expected`。  
系统约定：只输出 JSON；不要写 `status`；不要建议 `armed`（那是人的事）。

### 4.14 Overlay 测试

- 三种状态以外 → validate 失败。
- `blocked` 无 `reviewed_by` → 失败。
- fixture：支付/登录 `blocked`，业务切片 `armed`；`select main` 只含后者。
- generate 的单元测试用假 HTTP，断言写出的 status 是 `draft`。
- receipt 模块的测试：禁止 mock 成「模型写回执」。
- 无密钥的 select 在 CI 必须绿。

### 4.15 成功标准

与业务无关：一篇 inbox → 当天可审的一页；`blocked` 不红；select 无密钥可跑。  
LG fixture 另加：支付/登录 `blocked`；My Learning 已合部分可 `armed`。

---

## 5. 两件产品的组合

| 接入 | 结果 |
|---|---|
| 只 Forge | 开发有序，无需求对齐用例 |
| 只 Overlay | 有用例门，人仍可能直推 main |
| 都装 | Ruleset 可把 check 名 `overlay` 标 required；Overlay 红 ≠ 构建门红 |

允许的跨产品动作：

- 受 Forge 管的 agent：`workflow_dispatch` Overlay `generate`。
- 管理员：Ruleset required checks 同时勾构建门 + `overlay`。

禁止的跨产品动作：

- Forge apply 改 `suite.yaml`。
- Overlay workflow 改 Ruleset 或 `ci.yml`。
- 一个 wheel / 一个 tag 把两件产品绑死（发布分离）。

---

## 6. 技术栈（两件产品共用运行时，职责分开）

| 层 | 选用 | 不用 |
|---|---|---|
| 语言 | CPython 3.12+，源码写 Python | TS 做内核；Cython 当主写法；第一刀写 C |
| 包 | pip + `requirements.txt` + lock；两个包 `forge` / `overlay` 可同仓不同 entry | 第一刀 poetry/pdm |
| 契约 | YAML + pydantic v2 + JSON Schema | 数据库 |
| Forge 管仓 | GitHub Rulesets API + PR | 自建门户；HackMD 当管仓 |
| Overlay CI | Actions `setup-python` | 改接入方构建 YAML |
| LLM | OpenAI 兼容 HTTP，仅 generate | Deepseek3；push 时调用；强制 Ollama |
| Diff 审 | 接入方 CodeRabbit | Copilot review 当唯一门 |
| 写代码 agent | 接入方已有 Copilot/Cursor | 本产品自建舰队 |
| 后一刀执行 | 接入方已有测试命令 | Midscene / Shortest / Keploy |

CPython 能调 C。第一刀不写 C：生成卡模型和网络，select 扫几十个 yaml。

---

## 7. 本工作本布局

```text
forge/
  __init__.py / apply.py / status.py
  ruleset.protected-default.json
  agent-policy.md
  CODEOWNERS.example
  forge.example.yaml
overlay/
  __init__.py / validate.py / select.py / receipt.py / review.py / run.py / cover.py
schema/
  suite.schema.json
  inbox.schema.json
  inbox.example.md
  trace.schema.json
  trace.example.yaml
  receipt.example.yaml
  overlay-config 规则写在 design §4.6
prompts/extract.md
prompts/generate-cases.md
examples/learning-guide/
  inbox/
  suites/
  overlay.yaml
  forge.yaml
.github/workflows/
  forge-guard.yml
  overlay.yml
  overlay-check.yml      # 本仓自用：validate + select + run；兼跑 LG fixture
invariants.yaml          # 可选：跨叶子性质；本工作本有一份
docs/design.md           # 本文
docs/inbox.md            # Overlay 输入面
docs/test-spec.md        # 测试体系规格（两棵树 + 通用 function_id）
docs/agents/overlay-contract.md
docs/agents/ieee-test-system.md
schema/check.py          # 形状检查；不是产品 CLI
docs/products.md
docs/2026-09-10-对话整理.md
```

发布：`forge-v1.x` 与 `overlay-v1.x` 分 tag。接入方 pin tag。

---

## 8. 安全

- 不提交 `.env`、token、真实支付数据。
- Forge token 只在管理员本机或受保护的 `workflow_dispatch`。
- Overlay generate 的密钥：仓库 Secret；日志禁止打印 inbox 全文和模型原文（截断 + 打码）。
- Overlay run 禁止生产 host、禁止生产 Stripe/SES。
- Guard 与 select 无出站。
- Agent 政策与 `deny_paths` 挡住改构建门。

---

## 9. 切片

**第一刀（两件产品都能装到「任意仓」意义上成立）**

1. Overlay：`validate` + `select` + `run` + receipt + schema；blocked 不入选、不红。
2. `examples/learning-guide`：三篇 inbox（my-learning / payment / login）各对一个 suite；支付/登录 `blocked`。
3. Forge：默认 Ruleset JSON + `apply --dry-run` / 对测试仓 apply；agent-policy。
4. reusable overlay workflow：validate + select；`enable_run` 时在调用方 checkout 跑 `product_command`。
5. 本工作本 `overlay-check` 打开 `enable_run`；测试和 CI 同一条门。无 `generate` 也能用手写 suite 证明状态机。

**第二刀**

1. `overlay generate` 稳定（temperature=0，提示词入仓）。
2. `forge-guard.yml`。
3. 可选：select 按 PR 文件 ∩ `packages` 收窄 functional 集。

**以后**

- `subject: agent`、concurrency kind、组织级 Ruleset、Merge Queue 开关。
- 把 tag 回灌 `First-Light-TechHK/AIOps` 空仓当发布镜像（内容仍是这两件产品，不是 LG 业务）。

---

## 10. Learning Guide fixture（不是内核）

| LG 事实 | 落在哪 |
|---|---|
| Verify = Typecheck → Lint → Build and test | Forge `deny_paths`；Overlay 不 `workflow_call` |
| 七份 PRD 在 `docs/phase1/source-prd/*.docx` | inbox `source` pin，正文只摘录；测试规格不镜像七份目录 |
| 支付 / 登录未就绪 | suite `blocked` |
| My Learning 已合部分 | 可 `armed` |
| 测试栈 node:test + Playwright | 第二刀 `product_command`，不改成 Python |
| 生产域 `ilovelearningguide.com` | `forbid_hosts` |
| Proctor / Deepseek3 | 不 attach |

---

## 11. 实现验收清单

Forge

- [ ] `apply` 幂等；dry-run 不写远端。
- [ ] 保护分支禁直推、必须 PR；bypass 默认空。
- [ ] agent-policy 含「不改构建门 / 不写 armed」。
- [ ] 不创建接入方业务 job，不改 Verify 文件内容。

Overlay

- [ ] 状态只有三个；`select main` 不含 blocked/draft。
- [ ] generate 不在 push workflow。
- [ ] 回执只由 select/run 写。
- [ ] 无生产 URL；无 Proctor/Deepseek3 路径。
- [ ] LG fixture：支付/登录 blocked 时预演绿。
- [ ] 测试规格在 `suites/`；不另写按 PRD 章节镜像的规格书。
- [ ] `cases.md` / `trace.yaml` / 回执用接入方自选的 `function_id`；level 不是第二套编号。
- [ ] schema / 内核 / 设计例不把 `REQ-n`、FR 号段正则、`LOGIN-01` 或 IEEE 文件名写成法律。
- [ ] 内核 import 与设计例不出现 `LearningGuide` / `ilovelearningguide`（只许 examples/）。

组合

- [ ] 两包可独立安装。
- [ ] 文档写明可只装一件。
