---
name: design-cases
description: Design Overlay cases and define full cover as leaf triad plus declared invariants, with interaction only when leaves are coupled. This skill should be used when writing cases.md or invariants.yaml, running overlay cover, or asking how to catch global corner cases. Not line coverage and not a second PRD. Use with use-overlay.
metadata:
  short-description: Overlay triad, invariants, interactions
---

# Design Cases

Define Overlay “full cover” before writing any `cases.md`. Read [`docs/agents/overlay-contract.md`](../../docs/agents/overlay-contract.md), then this skill, then [`docs/test-spec.md`](../../docs/test-spec.md). IEEE subset: [`docs/agents/ieee-test-system.md`](../../docs/agents/ieee-test-system.md). Operate Overlay with [`../use-overlay/SKILL.md`](../use-overlay/SKILL.md).

Linked notes (same method, old path): [`docs/agents/case-design.md`](../../docs/agents/case-design.md).

## Lock / 不绿不能合

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

- armed 缺技法、invariant 未点名：`python -m overlay validate` / `cover` → CI **`overlay-check`**
- 不 NLP 判断「角想全了没有」。人看 `cover` 矩阵再决定 `blocked` / `armed`。
- 仓级禁令（push 不 generate）见 `python -m forge sop-lock` → **`sop-lock`**。

## Instructions

「标准化全覆盖」在 Overlay 里**不是**扫完产品 PRD，也不是行覆盖率，也不是叶子两两穷尽。

它是三层，缺一层就承认「还没设计完」：

| 层 | 标准化是什么 | 全局边角落在哪 |
|---|---|---|
| **叶子技法** | 每个 `function_id` 都有 Functional / Negative / Edge | 单功能的边界、失败、拒绝 |
| **不变量** | 每条已声明的 invariant 在某篇 `cases.md` 里被点名 | 必须读完整棵测试树才能看见的性质 |
| **交互** | 只对**已耦合**的叶子写一条 `span: interaction` | 两片叶子共享资源 / 状态 / 禁令时的组合 |

未切进任何 inbox 的 PRD 章 = 本测试树不管。那不是漏测，是没开刀。

`armed` 缺技法 → `validate` / `cover` 契约红。`draft` / `blocked` 可以薄，cover 只提示。

写任何一篇 `cases.md` 之前，**先读整个 overlay root**，不要只读当前 inbox：

1. 全部 `inbox/*.md`（In scope、Out of scope、Notes）
2. 全部 `suites/*/cases.md` 与 `suite.yaml` 状态
3. `invariants.yaml`（没有就先从设计非目标 / 状态机里列）
4. 接入方设计里「禁止 / 永不 / 不得」的句子

只读当前切片，写不出要求全局理解的 corner。那些角不在一片叶子的输入里。

然后按这个顺序编，不要跳：

### 1. 存货

列出本仓已有的 `function_id`。文档已有编号就抄，没有就铸。不要为 corner 再开 `E2E-B1` / `CROSS-01`。

### 2. 叶子三技法（本地标准化）

每个 `function_id` 一节 `## <id>`，下面三类 **`###` 标题必须原样是这三个词**（`armed` 必齐；大小写不敏感）：

```markdown
## AUTH-01
### Functional
### Negative
### Edge
```

| 技法 | `###` 标题 | 问什么 |
|---|---|---|
| Functional | `### Functional` | 声称可做的事做成了 |
| Negative | `### Negative` | 禁止、未授权、未就绪、明确失败 |
| Edge | `### Edge` | 重复、空、已完成、刚好越界、顺序颠倒 |

**不要**写 `### Depth`（契约不认，armed 会缺 Edge）。**不要**写 `## Specified / not tested now`（第一个词会变成 `function_id`）。`function_id` 在整个 overlay root 全局唯一。`invariants.yaml` 的 `function_ids` 必须对上已有 `##` 标题。

标题 / 步骤 / 期望。不要贴 PRD 验收原文交差。

### 3. 不变量（全局 corner 的住处）

把「整棵树必须永远为真」的性质写成 `invariants.yaml`，每条一个接入方自选的 id（内核例子用 `INV-one-charge`，不强制 `INV-` 前缀）。

典型来源（读完全部文档才会看见）：

- 状态机：`blocked` / `draft` 永不把 overlay-check 染红
- 跨产品：Forge 不写 `armed` / `reviewed_by`
- 安全：不打 `forbid_hosts`；push 不 `generate`
- 账本：回执只能 `select` / `run` 写
- 业务：同一 receipt 不双扣（fixture 例）

每条 invariant：

- `function_ids` 列出共同护住它的叶子（可以跨 suite）
- **必须**在某篇 `cases.md` 里以 token 出现（人能指着用例说这条性质）
- 主键仍是那个 `function_id`，不是第四套号

### 4. 交互（有耦合才写，禁止 N×N）

两片叶子只有在下面至少一条成立时才配一对：

- 同一篇 inbox 的 In scope 里并列
- 同一条 invariant 点了它们
- 共享 `packages`、同一份资源（会话、receipt、Ruleset）、或一条明确的「不得同时」

写法：用例挂在**会先失败的那片** `function_id` 下，技法仍是 F/N/E。`trace.yaml` 加：

```yaml
span: interaction
relates:
  - FN-other-leaf
```

不要发明平行主键。没有耦合就不要为「显得全」而写组合。

### 5. 人审

`cover` 打印矩阵。人看：缺技法、未点名的 invariant、该耦合却没有 `relates` 的提示。再决定 `blocked` 还是 `armed`。模型不 `armed`。

### Never

- Do not change LearningGuidePortal Verify. Do not attach / run / gate intern-workspace Proctor. Do not edit Deepseek3.
- Do not press production (`ilovelearningguide.com`). CI only; no CD.
- Do not generate on push. Do not arm as an agent. Do not write `reviewed_by` or receipts.
- Two products stay independent: do not let Forge write Overlay `status`.
- Do not vendor `forge/` / `overlay/` / `schema/` / `prompts/` into an adopter product commit repo.

## Examples

本工作本：

```text
python3 -m overlay cover --root .
# FN-overlay-select 三种技法齐
# INV-never-red-blocked 点名在 overlay-select 的 Negative（relates FN-overlay-generate）
```

Learning Guide fixture 的 `PAY-01` 可以有齐全技法，但 suite 是 `blocked`：设计完了，门禁不跑。

## Performance Notes

`cover` / `validate` 只扫本仓 YAML 和 Markdown。不跑产品、不调模型、不解析 docx。组合爆炸用「先声明耦合」挡住，不用全对。

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 总觉得还有没想到的角 | 先列 invariant，再写叶子。角是性质，不是更多章节。 |
| 想对所有 function_id 两两组合 | 停。没有耦合就不是测试项。 |
| 想用覆盖率 agent 证明跟了 PRD | 停。那不是 Overlay 的完成定义。 |
| armed 缺 Edge | 契约红。补 `### Edge`，不要改成 draft 躲，不要用 `### Depth` 顶替。 |
| 写了 `## Specified` | 契约红。改成段落。 |
| 跨套件重复 function_id | 契约红。换一个稳定唯一的 id。 |
| invariant 点了不存在的 `##` | 契约红。先对齐标题。 |
| 不知道 invariant 写哪 | 设计非目标、状态机、跨产品禁令。没有就先不建 `invariants.yaml`。 |
| 想给全局用例一个新号族 | 停。挂在已有 `function_id` 上，用 `span` + `relates`。 |
