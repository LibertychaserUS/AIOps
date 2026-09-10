# 测试体系规格

实现对照以本文 + [`design.md`](design.md) §4 为准。Inbox 合同见 [`inbox.md`](inbox.md)。Agent skill：[`agents/ieee-test-system.md`](agents/ieee-test-system.md)。读文档怎么编进契约：[`agents/overlay-contract.md`](agents/overlay-contract.md)。用例设计与覆盖：[`agents/case-design.md`](agents/case-design.md)。

Overlay 是**标准件**：冻契约（字段、状态、对齐方式），不冻某产品的编号、PRD 树、IEEE 文件名。人/agent 读接入方文档，编成契约形状。

测试体系**需要规格**。规格**追溯**产品意图，**不抄**文档形状。

---

## 1. 结论

| 问 | 答 |
|---|---|
| 测试体系要不要规格？ | 要。否则无法审、无法选、失败时说不清「哪条 PRD 功能 / 哪个测试节点」。 |
| 契约冻编号和目录吗？ | **不冻。** 接入方文档里已有什么编号、树什么形状，就读什么。 |
| 产品和测试是不是同一棵目录树？ | 不是。两棵树，形状不同，用同一个 `function_id` 对齐。 |
| 要不要另写一本「测试规格说明书」按 PRD 章节镜像？ | 不要。那是第二本 PRD，禁止。 |
| 要不要 IEEE 全套文档？ | **不要**二十份 Word。**要** IEEE 的识别 + 层次 + 双向追溯。 |

三份规格不要混：

| 规格 | 住哪 | 回答什么 | 跟随谁 |
|---|---|---|---|
| 产品 PRD / 设计 / FR | 产品仓（可是 docx） | 产品该做什么 | 产品自己的文档树 |
| Overlay **契约** | 本仓 `docs/` + `schema/` | 编进来之后长什么样 | **不**跟随任何产品目录或编号法 |
| 接入方 **测试规格** | `suites/<id>/` | 这一刀测哪些 `function_id`、跑不跑 | 追溯同一 inbox 钉死的 PRD 切片 |

本仓测 Overlay / Forge，对照 [`design.md`](design.md)，**不**对照 Learning Guide 的七份 PRD。LG 只出现在 [`examples/learning-guide/`](../examples/learning-guide/)。

内核 / `schema/` / 设计例只用通用形：`owner/name`、`FN-login-retry`。不要写某产品路由或域名。

---

## 2. 两棵树 + 对齐图

这是本规格的中心。

```text
Docs/PRD tree（产品）              Test tree（IEEE / Overlay）
PRD / design / FR / UC      <-->  function_id（同一个 id）
  function leaf             <-->  test item（同一个 function_id）
                                   ├ unit
                                   ├ integration
                                   ├ smoke
                                   ├ k6
                                   └ e2e
```

| 边 | 基数 | 说明 |
|---|---|---|
| PRD 章节 → test item | 0..n | 没切进 inbox 的章 = 本测试树不管 |
| test item → `function_id` | 恰好 1 | 一条测试节点只属于一个产品功能 |
| `function_id` → level | 0..n | 层次是同一 id 的面，不是第二套编号 |
| inbox 切片 → suite 目录 | 1:1 | `suites/<id>/` 是容器，不是 `function_id` |

失败时，人与 agent 必须能指着回执 / `cases.md` / 文件名说：**哪条 PRD 功能、哪个测试节点**。因此这三处都要带 `function_id`。

对齐是 **map**，不是 clone：不要把 PRD 目录抄成测试目录。

---

## 3. IEEE profile（子集）

采用 IEEE 829 与 ISO/IEC/IEEE 29119-1/2/3 的识别词。不采用它们的全套文档清单。

| IEEE 词 | 本仓 |
|---|---|
| test item | 一个 `function_id`（被测功能） |
| test condition | inbox In scope / 技法小节要行使的条件 |
| test case | `cases.md` 里一组输入、条件、期望 |
| test procedure | Steps |
| test level | `unit` \| `integration` \| `smoke` \| `k6` \| `e2e` |
| requirements traceability | `trace.yaml` 双向：PRD 功能 ↔ test item ↔ case |

`functional` / `negative` / `edge` 是测试**技法**（`trace.yaml` 字段名 `type`），挂在同一个 `function_id` 下面。

不写：Master Test Plan、Level Test Plan、环境规格书、异常报告模板、按 level 再出一本说明书。

---

## 4. `function_id`（契约，不是号段法律）

契约只问：非空；仓内作为叶子身份唯一；稳定；无空白。谁选字符串：**接入方**。文档已有则抄（`ML-FR-004`、`PAY-01`、`REQ-3`、`FN-login-retry` 都可以）。没有则铸。内核没有合法编号表。

schema **不得**把 `REQ-n`、`ML-FR-004`、`PAY-01`、`LOGIN-01` 或 `^[A-Z]{2,8}(-[A-Z]{1,6})?-[0-9]{2,3}$` 写成法律。

| 做 | 不做 |
|---|---|
| 和文档叶子用同一个 id | 再发明 `E2E-B1`、`UT-007` 当第二套主键 |
| inbox 行**可以**带上该 id | 规定必须像 `LOGIN-01` 或禁止 `FN-login-retry` |
| generate 沿用已有 id，没有则新铸 | 把 level 做成另一套号段 |
| 人审后 id 保持稳定 | 换文件名就换 id |

可选实例路径（接入方习惯，不是契约）：`<function_id>/<level>/…`。一篇 inbox 可以有多条叶子。suite 目录名不是 `function_id`。

---

## 5. 「跟随」指什么

**要跟随**

| 跟随 | 做法 |
|---|---|
| 意图 | inbox 的 Intent / In scope / User cases 变成 `cases.md` 里的 `function_id` 节 |
| 范围 | Out of scope 不得变成 test item，不得被 select 跑 |
| 编号 | 与 PRD 功能同一 `function_id`；level 只当面 |
| 来源 | `suite.yaml` 的 `source` = `inbox/<id>.md`；inbox 若声明 `source`，pin 到产品仓路径 + ref |
| 就绪 | inbox `readiness: not-ready` → 人审应标 `blocked`；不得因为 PRD 写了验收标准就 `armed` |
| 变更 | 产品仓 PRD 更新：人改 inbox 摘录和 `source.ref`，再 generate / 手改 cases，重新审 |

**不跟随**

| 不跟随 | 原因 |
|---|---|
| PRD 章节树 / 目录 | 一篇 inbox 只切一块。 |
| PRD 文件格式 | Overlay 不解析 docx；不把 PRD 当 schema。 |
| 某产品的路由 / 域名 | 只许 fixture。内核例子用 `FN-login-retry`，不用 LG 路径。 |
| PRD 版本号锁死 | 用 `source.ref` pin，不搞双版本书。 |
| PRD 验收标准原文当用例 | 用例要有步骤和期望。 |
| 全 PRD 覆盖义务 | 未切进 inbox = 不管。 |
| 产品仓已有测试文件树 | `product_command` 调用；本工作本的测试就是 Overlay CI。 |

「PRD 更新了，测试规格自动长成新章节」第一刀不做。

---

## 6. 接入方测试规格就是 suite 目录

不要第四个文件 `suites/<id>/spec.md` 或仓根 `测试规格说明书.md`。`suites/<id>/` 就是测试树的这一刀实例。

```text
suites/<id>/suite.yaml    # 机器规格：状态、种类、审核、source
suites/<id>/cases.md      # 人读规格：function_id + 技法
suites/<id>/trace.yaml    # 可选：function_id × level → case
```

`inbox/<id>.md` 不是测试规格，是**请生成规格**的输入。`select` / `run` 不读 inbox，只读 suite。

---

## 7. 需求条怎么来

```text
产品 PRD（大、可二进制）
    │  人摘录，pin ref；抄或铸造 function_id
    ▼
inbox In scope（行首 function_id）
    │  generate 或人手写
    ▼
cases.md  ## <function_id> <一句话>
    │  每条下面三类技法
    ▼
Functional / Negative / Edge
    │  可选实例
    ▼
<function_id>/<level>/<seq>
```

规则：

1. `function_id` 只来自**同一篇** inbox 的 In scope（或 User cases 行首）。
2. 标题是一句话功能，不是 PRD 章名。
3. `armed` 的每个 `function_id` 必须三种技法齐（Functional / Negative / Edge）。`draft` / `blocked` 可以薄，`cover` 只提示。
4. In scope 有几行带 id，generate 就抽几条。
5. `kind: user-case`：场景行首同样带 `function_id`。
6. `kind: figma-ref`：第一刀只出对照说明；若有 In scope，行首仍要 id。
7. 全局边角写成 `invariants.yaml` + 用例点名；交互用 `trace.yaml` 的 `span` / `relates`。方法：[`agents/case-design.md`](agents/case-design.md)。

可选 `trace.yaml`（[`schema/trace.schema.json`](../schema/trace.schema.json)）：

```yaml
schema: overlay-trace/v1
suite: checkout-retry
items:
  - function_id: FN-login-retry
    case_id: FN-login-retry/functional
    type: functional
    level: unit
    type: functional
```

第一刀：有文件就校验形状；没文件不红。回执的 `selected` / `ran` 应带 `function_id`（能带 `level` 则带）。模型不得写回执。

---

## 8. 覆盖（测试体系自己的完成定义）

「覆盖了」是三层，不是一层：

| 层 | 完成定义 | 谁检查 |
|---|---|---|
| 叶子 | 已切进 inbox 的每条 `function_id` 有一节；`armed` 则 Functional / Negative / Edge 齐 | `validate` / `cover` |
| 不变量 | `invariants.yaml` 里每条 id 在某篇 `cases.md` 被点名；列出的 `function_ids` 都存在 | 有该文件才查 |
| 交互 | 已耦合的叶子有一条 `span: interaction`（或正文点到兄弟 id） | `cover` 提示；不穷尽两两 |

不表示：PRD 每一章都有用例；产品 Verify 已实现步骤；行覆盖率；叶子笛卡尔积；支付/登录写进 PRD 就必须 `armed`。

要求对**全局理解**的 corner 不住在单条 In scope 里。它们是跨叶子的性质（状态机、跨产品禁令、同一资源的组合）。写法：先读完整棵 overlay root，再声明 invariant / interaction。不要为此再开一套 `CROSS-01` 主键。

`python -m overlay cover --root .` 打印矩阵。CI 的 `validate` 已含 `armed` 技法与 invariant 点名。

---

## 9. PRD 变了，规格怎么跟

人改 inbox 的 `source.ref` + 摘录；`function_id` 保持稳定。重新 generate 只许变成/保持 `draft`。禁止 CI 见 PRD 路径变了就重写 `cases.md`。禁止模型改 `reviewed_by`。禁止改已登记的 `function_id` 去「重排号」。

---

## 10. Overlay / Forge 自己的测试规格

本仓 `overlay-check` 对照 [`design.md`](design.md)，不对照任何产品 PRD。fixture 只证明元规格能装到一个像真的接入方上。

---

## 11. 校验（`overlay validate`）

1. 有 suite 则 `suite.yaml.source` == `inbox/<id>.md`。
2. `cases.md` 非空。`armed` 至少一条以 `function_id` 开头的 `##` 标题（非空、无空白）。`blocked`/`draft` 允许很薄。
3. 不得把 `status: armed` 写进用例正文当门。
4. **不**因为 In scope 没有 id、或 id 不像 FR 号 / `LOGIN-01` 而红。有 id 则须无空白。
5. `cases.md` 的 `function_id` 标题必须能在同一篇 inbox 的 In scope（或 User cases 行首）找到；Out of scope 不得当标题。
6. 若有 `trace.yaml`：符合 schema；`suite` 等于目录名；`function_id` 能在 `cases.md` 找到；`level` ∈ `unit`\|`integration`\|`smoke`\|`k6`\|`e2e`；`type` ∈ `functional`\|`negative`\|`edge`；若有 `relates`，那些 id 必须是本 overlay root 里某片叶子。
7. `armed` 缺技法 → 红。`draft` / `blocked` 缺技法不红。
8. 若有 `invariants.yaml`：符合 schema；每条 `function_ids` 都能在某篇 `cases.md` 找到；每条 `id` 必须作为 token 出现在某篇 `cases.md`。
9. 不因为「产品仓还有没切的 PRD」而红。
10. 不因为产品仓历史文件还叫 `E2E-B1` / `LOAD-001` 而红；本仓 fixture 不得再发明这种平行号族。

契约红（退出码 2）≠ 业务功能红。

第一刀形状检查：[`schema/check.py`](../schema/check.py)。不要为此实现产品 CLI。

---

## 12. 非目标

- IEEE / ISO **全套**测试计划、策略书、环境规格另开文件树。识别 / 层次 / 追溯 **是**目标。
- 按产品仓七份 PRD 各生一本测试规格。
- 把 PRD 验收标准原文当 `cases.md` 主体。
- 用覆盖率 agent 证明「跟随了 PRD」。
- 为全局 corner 再开 `CROSS-01` / `E2E-B1` 主键，或对所有叶子两两穷尽。
- 测试规格驱动改产品 Verify。
- Overlay 元规格里出现某产品的路由或域名（只许 fixture）。
- 为 unit / e2e / k6 各做一套主键（`E2E-B1` vs `UT-007` vs `LOAD-001`）。
- 内核 schema 写死某产品的 `ML-FR-*` 清单，或把 FR / `LOGIN-01` 号段正则写成法律。

---

## 13. Learning Guide fixture

只举例。这些 id 住在产品仓测试与 handbook 注释里；Overlay 内核不得写死 LG 路由。

| function_id | 产品叶子（PRD / 实践） | Overlay 落点 | 备注 |
|---|---|---|---|
| `ML-FR-004` | My Learning 课程卡片 | `inbox/my-learning.md` → `cases.md` | 产品仓 `tests/unit/ML-FR-004-006-course-cards.test.ts` |
| `ML-FR-007` | Unique LP progress | 同上 inbox 第二条 In scope | 产品仓 `ML-FR-007-unique-lp-progress.test.ts` |
| `PAY-01` | 付款后权益（未就绪） | `inbox/payment.md`；suite `blocked` | 产品仓 `PAY-stripe.skip.spec.ts` 已占 `PAY-01`…`PAY-07` |
| `AUTH-01` | 有效会话看自己的数据 | `inbox/login.md`；suite `blocked` | 不要写成 `E2E-B1-004` |
| `LEARN-02` | 已购未学不造卡片 | 与 `ML-FR-004` 对齐的设计锁；本 fixture 不另开 suite | 产品仓 unit 文件名已用 `LEARN-02` |
| `KS-01` | 未登录 KS API 必须 401 | 未切进本 fixture 三篇 inbox | 产品仓 `KS-01-unauth-api.spec.ts` |
| `AUTH-05` | 会话门（LG 号族） | 未切 | 以后切仍用此号，不新开 e2e 号族 |

反例（历史，不要学进 Overlay）：

| 反例 | 为什么错 |
|---|---|
| `E2E-B1-007` | 平行号族。同一条应是 `LEARN-02/e2e/01` 或 `ML-FR-004/e2e/01` |
| `LOAD-001`…`004` | k6 stub 自编号。有 SLA 之后应是对应功能的 `/k6/` 实例（付款负载 → `PAY-01/k6/01`） |

| suite | 状态 | 追溯 | 不追溯 |
|---|---|---|---|
| `my-learning` | `armed` + `ML-FR-004` / `ML-FR-007` | inbox 摘录的卡片与进度 | 整份 My Learning docx |
| `payment` | `blocked` + `PAY-01` | inbox 里「付款后权益更新」 | 整份 Payment PRD、真卡、生产 webhook |
| `login` | `blocked` + `AUTH-01` | inbox 里「有效会话看自己的数据」 | 整份 Registration/Auth PRD |

三篇 inbox、三份测试规格。不是一份 PRD 规格派生三份镜像文档。
