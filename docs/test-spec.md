# 测试体系规格

实现对照以本文 + [`design.md`](design.md) §4 为准。Inbox 合同见 [`inbox.md`](inbox.md)。

测试体系**需要规格**。规格**追溯**产品 PRD 的切片，**不抄** PRD 的文档规格。

---

## 1. 结论

| 问 | 答 |
|---|---|
| 测试体系要不要规格？ | 要。否则 `generate` 出来的页无法审、无法选、无法解释「跟哪条需求有关」。 |
| 要不要跟随 PRD 规格？ | **跟随意图和范围，不跟随文档形状。** |
| 要不要另写一本「测试规格说明书」按 PRD 章节镜像？ | 不要。那是第二本 PRD，第一刀禁止。 |

三份规格不要混：

| 规格 | 住哪 | 回答什么 | 跟随谁 |
|---|---|---|---|
| 产品 PRD | 产品仓（可是 docx） | 产品该做什么 | 产品自己的 |
| Overlay **元规格** | 本仓 `docs/` + `schema/` | 任意接入方的测试体系长什么样 | **不**跟随任何产品 PRD |
| 接入方 **测试规格** | `suites/<id>/` | 这一刀测什么、跑不跑 | 追溯同一 `id` 的 inbox → 钉死的 PRD 切片 |

本仓测 Overlay / Forge，对照 [`design.md`](design.md)，**不**对照 Learning Guide 的七份 PRD。

---

## 2. 「跟随」指什么

**要跟随**

| 跟随 | 做法 |
|---|---|
| 意图 | inbox 的 Intent / In scope / User cases 变成 `cases.md` 里的 `REQ-n` |
| 范围 | Out of scope 不得变成 `REQ-n`，不得被 select 跑 |
| 来源 | `suite.yaml` 的 `source` = `inbox/<id>.md`；inbox 若声明 `source`，pin 到产品仓路径 + ref |
| 就绪 | inbox `readiness: not-ready` → 人审应标 `blocked`；不得因为 PRD 里写了验收标准就 `armed` |
| 变更 | 产品仓 PRD 更新：人改 inbox 摘录和 `source.ref`，再 generate / 手改 cases，重新审 |

**不跟随**

| 不跟随 | 原因 |
|---|---|
| PRD 章节树 / 目录 | 七份 docx 的目录不是测试目录。一篇 inbox 只切一块。 |
| PRD 文件格式 | Overlay 不解析 docx；不把 PRD 当 schema。 |
| PRD 版本号锁死 | 不维护「PRD v1.0 ↔ 测试规格 v1.0」。用 `source.ref` pin，不搞双版本书。 |
| PRD 验收标准原文当用例 | 验收标准是产品语言。用例要有步骤和期望，给人审，不是把 AC 粘过去。 |
| 全 PRD 覆盖义务 | 没有「每章必须有 suite」。未切进 inbox 的章节 = 本测试体系不管。 |
| 产品仓已有测试文件树 | 第二刀最多调 `product_command`；不把 `cases.md` 按 Playwright 目录重排。 |

「PRD 更新了，测试规格自动长成新章节」第一刀不做。那是解析 docx + 一对多，已冻结。

---

## 3. 接入方测试规格就是 suite 目录

不要第四个文件 `suites/<id>/spec.md` 或仓根 `测试规格说明书.md`。

```text
suites/<id>/suite.yaml    # 机器规格：状态、种类、审核、source
suites/<id>/cases.md      # 人读规格：REQ-n + 功能/负面/边界
suites/<id>/trace.yaml    # 可选：REQ → case；第一刀不强制
```

| 文件 | 规格角色 |
|---|---|
| `suite.yaml` | 这份测试规格能不能进门（`draft`/`blocked`/`armed`） |
| `cases.md` | 这份测试规格的正文 |
| `trace.yaml` | 正文和需求条的机器对照 |

`inbox/<id>.md` 不是测试规格，是**请生成规格**的输入。`select` / `run` 不读 inbox，只读 suite。

`blocked` 的 suite 可以正文很薄：规格已经存在（「已审、不跑、不当红」）。未 generate 的 inbox 还没有测试规格，这不是错。

---

## 4. 需求条怎么来

```text
产品 PRD（大、可二进制）
    │  人摘录，pin ref
    ▼
inbox In scope / User cases
    │  generate 或人手写
    ▼
cases.md  ## REQ-<n> <一句话>
    │  每条下面三类
    ▼
Functional / Negative / Edge
```

规则：

1. `REQ-n` 只来自**同一篇** inbox，不从产品仓目录扫出来。
2. 编号从 1 起，连续；标题是一句话需求，不是 PRD 章名。
3. 每条 `REQ-n` 至少一类用例（第一刀建议三类都有，缺一类不契约红）。
4. 一条 inbox 的 In scope 有几行，generate 就抽几条；不要把整本 PRD 展成几十条。
5. `kind: user-case`：User cases 编号场景是主体，仍写成 `REQ-n`（一场景一条）。
6. `kind: figma-ref`：第一刀只出对照说明型 REQ，不出视觉断言脚本。

可选 `trace.yaml`（JSON Schema：[`schema/trace.schema.json`](../schema/trace.schema.json)）：

```yaml
schema: overlay-trace/v1
suite: my-learning
items:
  - requirement_id: REQ-1
    case_id: REQ-1/functional
    type: functional
```

第一刀：有文件就校验形状；没文件不红。第二刀以后才谈「armed 必须有 trace」。

---

## 5. 覆盖（测试体系自己的完成定义）

「覆盖了」在 Overlay 里只表示：

1. 这篇 inbox 的 In scope 每条都有对应 `REQ-n`（人手写或 generate 后人对过）。
2. 人审过 `suite.yaml`。
3. 若 `armed`：声称这些 REQ 对应的代码可测。

不表示：

- 产品仓 PRD 每一章都有用例。
- 产品 Verify / Playwright 已经实现这些步骤。
- 覆盖率百分比。
- 支付/登录因为写进了 PRD 就必须 `armed`。

缺口怎么看：人看 `cases.md` 和 inbox In scope。`trace.yaml` 是后援，不是门。

---

## 6. PRD 变了，规格怎么跟

```text
产品仓 PRD 改了
    │
    ▼
人改 inbox：source.ref + 摘录（新 PR）
    │  generate 不改 inbox
    ▼
overlay generate --inbox inbox/<id>.md
    │  已是 blocked/armed → 拒绝，除非 --force-draft
    ▼
人重新审 suite.yaml
```

| 谁改 | 改什么 |
|---|---|
| 产品改大 PRD | 产品仓。Overlay 第一刀不自动拉。 |
| 人认定切片变了 | inbox。测试规格暂时旧，直到重新 generate 或手改 cases。 |
| generate | 只许把 suite 写成/保持 `draft`。 |
| 人审 | 只改 `suite.yaml` 状态字段。 |

禁止：CI 看见产品仓 PRD 路径变了就重写 `cases.md`。禁止模型改 `reviewed_by`。

---

## 7. Overlay / Forge 自己的测试规格

本仓 `self-test` 测的是两件产品，不是接入方业务。

对照：[`design.md`](design.md) 的 CLI、状态机、退出码、§4.14。

不对照：Learning Guide PRD、产品路由、产品 Playwright。

fixture `examples/learning-guide/` 只证明「元规格能装到一个像真的接入方上」。支付/登录 `blocked` 是元规格的例子，不是「按 Payment PRD 写完测试规格」。

---

## 8. 校验（`overlay validate`）

在 inbox / suite 已有规则之外，测试规格相关：

1. `suites/<id>/` 若存在：`suite.yaml.source` == `inbox/<id>.md`（inbox 可以还没有，但有 suite 则必须有对应 inbox——第一刀要求两边成对，见 inbox §7.10 的逆命题：有 suite 必有 inbox）。
2. `cases.md` 存在且非空。`blocked`/`draft` 允许正文很短；`armed` 至少一条 `## REQ-` 标题。
3. `cases.md` 不得出现第四种状态词当标题（不把 `status: armed` 写进用例正文当门）。
4. 若有 `trace.yaml`：符合 schema；`suite` 等于目录名；`requirement_id` 能在 `cases.md` 找到同名标题；`type` ∈ `functional`\|`negative`\|`edge`。
5. 不因为「产品仓还有五份没切的 PRD」而红。

契约红（退出码 2）≠ 业务功能红。

---

## 9. 非目标

- IEEE / ISO 测试计划、策略书、环境规格另开一套文件树。
- 按产品仓 `docs/phase1/source-prd/` 七份各生一本测试规格。
- 把 PRD 验收标准原文提交成 `cases.md` 主体。
- 用覆盖率 agent 证明「跟随了 PRD」。
- 测试规格驱动改产品 Verify。
- Overlay 元规格里出现某产品的路由或域名（只许 fixture）。

---

## 10. Learning Guide fixture

| suite | 测试规格状态 | 追溯 | 不追溯 |
|---|---|---|---|
| `my-learning` | `armed` + 有 `REQ-1` | inbox 摘录的 overview / progress | 整份 My Learning docx |
| `payment` | `blocked` + 可有薄 REQ | inbox 里「付款后权益更新」这一刀 | 整份 Payment PRD、真卡、生产 webhook |
| `login` | `blocked` + 可有薄 REQ | inbox 里「有效会话看自己的数据」 | 整份 Registration/Auth PRD |

三篇 inbox、三份测试规格。不是一份 PRD 规格派生三份镜像文档。
