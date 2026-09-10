# 测试体系规格

实现对照以本文 + [`design.md`](design.md) §4 为准。Inbox 合同见 [`inbox.md`](inbox.md)。编译技能：[`agents/overlay-contract.md`](agents/overlay-contract.md)。IEEE 剖面：[`agents/ieee-test-system.md`](agents/ieee-test-system.md)。

Overlay 是**标准件**。冻的是**契约**（字段、文件角色、状态机、对齐方式），不是某产品的编号、PRD 章节树、IEEE 表单名、或测试目录怎么排。人/agent **读**接入方文档，**编**成契约形状。

测试体系**需要规格**。规格**追溯**产品意图，**不抄**文档形状。

---

## 1. 结论

| 问 | 答 |
|---|---|
| 测试体系要不要规格？ | 要。否则无法审、无法选、失败时说不清是哪片叶子。 |
| 契约冻编号和目录吗？ | **不冻。** 接入方文档里已有什么编号、树什么形状，就读什么。 |
| 产品和测试是不是同一棵目录树？ | 不是。两棵树，形状不同，用同一个接入方自选的 `function_id` 对齐。 |
| 要不要另写一本「测试规格说明书」按 PRD 章节镜像？ | 不要。那是第二本 PRD，禁止。 |
| 要不要 IEEE 全套文档？ | **不要**二十份 Word。**要**识别 + 层次 + 双向追溯。 |

三份规格不要混：

| 规格 | 住哪 | 回答什么 | 跟随谁 |
|---|---|---|---|
| 产品 PRD / 设计 / 已有测试 | 接入方仓（可是 docx） | 产品该做什么 | 接入方自己的文档树 |
| Overlay **契约** | 本仓 `docs/` + `schema/` | 编进来之后长什么样 | **不**跟随任何产品目录或编号法 |
| 接入方 **测试规格** | `suites/<id>/` | 这一刀测哪些叶子、跑不跑 | 追溯同一 inbox；叶子用 `function_id` |

本仓测 Overlay / Forge，对照 [`design.md`](design.md)，**不**对照任何一家产品的 PRD。Learning Guide 只出现在 [`examples/learning-guide/`](../examples/learning-guide/) 这份**已编译 fixture**。

内核 / `schema/` / 设计例只用通用形：`owner/name`、`FN-login-retry`。不要写某产品路由或域名。

---

## 2. 两棵树 + 对齐图

```text
接入方文档树                         接入方测试树
PRD / design / inbox 摘录            unit / integration / smoke / k6 / e2e
        │                                        │
        │  叶子：同一 function_id                 │  level 只是面，不是第二套号
        └──────────── FN-login-retry ────────────┘
```

| 边 | 基数 | 说明 |
|---|---|---|
| PRD 章节 → test item | 0..n | 没切进 inbox 的章 = 本测试树不管 |
| test item → `function_id` | 恰好 1 | 一条测试节点只属于一片叶子 |
| `function_id` → level | 0..n | 层次是同一 id 的面，不是第二套编号 |
| inbox 切片 → suite 目录 | 1:1 | `suites/<id>/` 是容器，不是 `function_id` |

失败时，人与 agent 必须能指着回执 / `cases.md` 说：**是哪片叶子的问题**。因此 inbox 行（或 source pin）和标题 / `trace.yaml` 写同一个字符串。

对齐是 **map**，不是 clone：不要把 PRD 目录抄成测试目录。

---

## 3. IEEE profile（子集）

采用 IEEE 829 与 ISO/IEC/IEEE 29119-1/2/3 的识别词。不采用它们的全套文档清单。

| IEEE 词 | 本仓 |
|---|---|
| test item | 一个 `function_id`（被测叶子） |
| test condition | inbox In scope / 技法小节要行使的条件 |
| test case | `cases.md` 里一组输入、条件、期望 |
| test procedure | Steps |
| test level | `unit` \| `integration` \| `smoke` \| `k6` \| `e2e`（可选面） |
| requirements traceability | `trace.yaml` 双向：文档叶子 ↔ test item ↔ case |

`functional` / `negative` / `edge` 是测试**技法**（`trace.yaml` 字段名 `type`），挂在同一个 `function_id` 下面。

不写：Master Test Plan、Level Test Plan、环境规格书、异常报告模板、按 level 再出一本说明书。

---

## 4. `function_id`（契约，不是号段法律）

契约只问四件事：

1. **非空**
2. **仓内唯一**（同一字符串 = 同一片叶子）
3. **稳定**
4. **无空白**

谁选字符串：**接入方**。文档已有则抄（`ML-FR-004`、`PAY-01`、`REQ-3`、`FN-login-retry` 都可以）。没有则铸。内核没有合法编号表。

schema **不得**把下面这些写成法律：`REQ-n`、`ML-FR-004`、`PAY-01`、`AUTH-01`、`LOGIN-01`，或 `^[A-Z]{2,8}(-[A-Z]{1,6})?-[0-9]{2,3}$`。那些只是某接入方可能用的形状。

| 做 | 不做 |
|---|---|
| 和文档叶子用同一个 id | 再发明 `E2E-B1`、`UT-007` 当第二套主键 |
| inbox 行**可以**带上该 id | 规定必须像 `LOGIN-01` 或禁止 `FN-login-retry` |
| generate 沿用已有 id，没有则新铸 | 把 level 做成另一套号段 |
| 人审后 id 保持稳定 | 换文件名就换 id |

可选实例路径（接入方习惯，不是契约）：`<function_id>/<level>/…`。

一篇 inbox 可以有多条叶子。suite 目录名与 `function_id` 是两套东西。

---

## 5. 「跟随」指什么

**要跟随**

| 跟随 | 做法 |
|---|---|
| 意图 | inbox 的 Intent / In scope / User cases 编成 `cases.md` 叶子 |
| 范围 | Out of scope 不得变成 test item，不得被 select 跑 |
| 已有 id | 接入方文档或 inbox 行已经写了 id，就**沿用** |
| 来源 | `suite.yaml` 的 `source` = `inbox/<id>.md`；inbox 若声明 `source`，pin 到产品仓路径 + ref |
| 就绪 | inbox `readiness: not-ready` → 人审应标 `blocked`；不得因为 PRD 写了验收标准就 `armed` |
| 变更 | 人改 inbox 摘录和 `source.ref`，再 generate / 手改 cases，重新审 |

**不跟随**

| 不跟随 | 原因 |
|---|---|
| PRD 章节树 / 目录 | 一篇 inbox 只切一块。 |
| PRD 文件格式 | Overlay 不解析 docx；不把 PRD 当 schema。 |
| 产品编号法 | 不把 FR / REQ / IEEE 表号写成内核法律。 |
| 某产品的路由 / 域名 | 只许 fixture。内核例子用 `FN-login-retry`。 |
| PRD 版本号锁死 | 用 `source.ref` pin。 |
| PRD 验收标准原文当用例 | 用例要有步骤和期望。 |
| 全 PRD 覆盖义务 | 未切进 inbox = 不管。 |
| 产品仓已有测试文件树 | 第二刀最多调 `product_command`。 |

「PRD 更新了，测试规格自动长成新章节」第一刀不做。

---

## 6. 接入方测试规格就是 suite 目录

不要第四个文件 `suites/<id>/spec.md` 或仓根「测试规格说明书」。

```text
suites/<id>/suite.yaml    # 机器规格：状态、种类、审核、source
suites/<id>/cases.md      # 人读规格：function_id + 技法
suites/<id>/trace.yaml    # 可选：function_id × level → case
```

`inbox/<id>.md` 不是测试规格，是**请生成规格**的输入。`select` / `run` 不读 inbox，只读 suite。

---

## 7. 叶子怎么来（读文档，编成契约）

```text
接入方 PRD / 设计 / 已有测试（形状随便）
    │  人 or agent 读，摘进 inbox；已有 id 就抄上
    ▼
inbox In scope / User cases   （一行可以带 function_id）
    │  generate 或人手写 —— 无写死 FR 表
    ▼
cases.md  ## <function_id> <一句话>
    │  每条下面三类技法
    ▼
Functional / Negative / Edge     level 是面，另写在 trace
```

规则：

1. 叶子只来自**同一篇** inbox，不从产品仓目录扫出来，也不从本仓一张功能目录表取。
2. 标题是一句话需求，不是 PRD 章名。第一段是 `function_id`。
3. 每个 test item 至少一类技法（缺一类第一刀不契约红）。
4. In scope 有几行要对齐的，就编几条叶子。
5. `kind: user-case`：一场景一条叶子。
6. `kind: figma-ref`：第一刀只出对照说明。

`generate`：**读 inbox，吐契约合法文件**。禁止在 Overlay 源码里写死某产品的 FR 清单。

可选 `trace.yaml`（[`schema/trace.schema.json`](../schema/trace.schema.json)）：

```yaml
schema: overlay-trace/v1
suite: checkout-retry
items:
  - function_id: FN-login-retry
    case_id: FN-login-retry/functional
    type: functional
    level: unit
```

第一刀：有文件就校验形状；没文件不红。`level` 可缺。回执能带 `function_id` 则带。模型不得写回执。

---

## 8. 覆盖（测试体系自己的完成定义）

「覆盖了」只表示：这篇 inbox 要对齐的 In scope 每条都有对应 `function_id` 节；人审过 `suite.yaml`；若 `armed` 则声称这些叶子可测。

不表示：PRD 每一章都有用例；产品 Verify 已实现步骤；覆盖率百分比；某条产品编号写进 PRD 就必须 `armed`。

---

## 9. 文档变了，规格怎么跟

人改 inbox 的 `source.ref` + 摘录；已有 `function_id` 尽量保持。重新 generate 只许变成/保持 `draft`。禁止 CI 见 PRD 路径变了就重写 `cases.md`。禁止模型改 `reviewed_by`。禁止 generate 把接入方 id 改写成内核目录号。

---

## 10. Overlay / Forge 自己的测试规格

本仓 `self-test` 对照 [`design.md`](design.md)，不对照任何产品 PRD。fixture 只证明契约能装下一份已经编好的接入方例子。

---

## 11. 校验（`overlay validate`）

1. 有 suite 则 `suite.yaml.source` == `inbox/<id>.md`。
2. `cases.md` 非空。`armed` 至少一条以 `function_id` 开头的 `##` 标题（非空、无空白）。`blocked`/`draft` 允许很薄。
3. 不得把 `status: armed` 写进用例正文当门。
4. **不**因为 In scope 行没有 id、或 id 不像 `REQ-n` / FR 号 / `LOGIN-01` 而红。有 id 则须无空白，并与 `cases.md` 标题一致。
5. **不**因为标题是 `REQ-1` 或 `FN-login-retry` 而红（接入方可以选这些字符串）。
6. 若有 `trace.yaml`：符合 schema；`suite` 等于目录名；`function_id` 能在 `cases.md` 找到；若有 `level` 则 ∈ 枚举；`type` ∈ `functional`\|`negative`\|`edge`。
7. 不因为「产品仓还有没切的章节」而红。

契约红（退出码 2）≠ 业务功能红。

第一刀形状检查：[`schema/check.py`](../schema/check.py)。不要为此实现产品 CLI。

---

## 12. 非目标

- IEEE / ISO **全套**测试计划文件树。识别 / 层次 / 追溯 **是**目标。
- 按某产品仓每一份 PRD 各生一本镜像规格。
- 把 PRD 验收标准原文当 `cases.md` 主体。
- 在 schema 或内核写死 FR / REQ / `LOGIN-01` 号段。
- 用覆盖率 agent 证明「跟随了 PRD」。
- 测试规格驱动改产品 Verify。
- Overlay 内核或设计例里出现某产品的路由或域名（只许 fixture）。
- 为 unit / e2e / k6 各做一套主键。

---

## 13. Learning Guide fixture（已编译例，不是内核）

这些 id 住在 fixture 里，证明「读接入方文档 → 编成契约」。**不是** Overlay 的合法编号表。

| function_id | 产品叶子 | Overlay 落点 | 备注 |
|---|---|---|---|
| `ML-FR-004` | My Learning 课程卡片 | `inbox/my-learning.md` → `cases.md` | 编译自产品仓已有编号 |
| `ML-FR-007` | Unique LP progress | 同上 inbox 第二条 | 同上 |
| `PAY-01` | 付款后权益（未就绪） | `inbox/payment.md`；suite `blocked` | 同上 |
| `AUTH-01` | 有效会话看自己的数据 | `inbox/login.md`；suite `blocked` | 同上 |
| `LEARN-02` | 已购未学不造卡片 | 与 `ML-FR-004` 对齐的设计锁；本 fixture 不另开 suite | 产品仓已有此号则沿用 |
| `KS-01` | 未登录 KS API 必须 401 | 未切进本 fixture 三篇 inbox | 以后切仍用接入方此号 |

| suite | 状态 | 追溯 | 不追溯 |
|---|---|---|---|
| `my-learning` | `armed` + `ML-FR-004` / `ML-FR-007` | inbox 摘录的卡片与进度 | 整份 My Learning docx |
| `payment` | `blocked` + `PAY-01` | inbox 里「付款后权益更新」 | 整份 Payment PRD、真卡、生产 webhook |
| `login` | `blocked` + `AUTH-01` | inbox 里「有效会话看自己的数据」 | 整份 Registration/Auth PRD |

三篇 inbox、三份测试规格。别的接入方换自己的文档和自己的 id，不改 Overlay 源码。
