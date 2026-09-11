# Overlay 契约：读文档，编成 schema

给人和 agent 的技能说明。权威契约是 [`../overlay-contract.md`](../overlay-contract.md)。**不是**某一家产品的技能，也不含该产品的编号表、路由、域名。现状：[`../STATE.md`](../STATE.md)。

IEEE 剖面与两棵树：[`ieee-test-system.md`](ieee-test-system.md)。对照：[`../test-spec.md`](../test-spec.md)、[`../inbox.md`](../inbox.md)、[`../design.md`](../design.md) §4、[`../../schema/`](../../schema/)。

---

## Instructions

Overlay 是标准件。你冻的是契约，不是接入方怎么给章节、用例、IEEE 表单编号。

1. **先读接入方文档**，不要先发明目录。读 PRD、设计、inbox、已有测试。不要改产品仓已有的构建 workflow，不要打 `forbid_hosts` 里的生产域名。
2. **编成契约形状**，不要重排对方的树：`inbox/<id>.md` → `suites/<id>/suite.yaml` + `cases.md` + 可选 `trace.yaml`。
3. **id 接入方说了算。** 文档里已有任何稳定无空白字符串，就抄进 inbox 行和标题。没有就铸（内核例子用 `FN-login-retry`）。内核没有号段。
4. **两棵树只对齐叶子。** 同一 `function_id`；`level` 是面，不是第二套号。
5. **IEEE 只取剖面。** identification、levels、trace。不要交二十份 Word。
6. **`generate` 只编译。** 读 inbox，吐出契约合法文件。禁止写死 FR 表。v2 缺省 `status: active`。
7. **不要越权。** 不写回执，不把别人的套件改成 `blocked`。
8. **用例怎么设计。** 先读完整棵 overlay root，再写当前 suite。`active` 三种技法齐。全局 corner 进 `invariants.yaml` 并在 `cases.md` 点名。有耦合才写 `span: interaction` + `relates`。方法：[`../../skills/design-cases/SKILL.md`](../../skills/design-cases/SKILL.md)（旧入口 [`case-design.md`](case-design.md)）。

`function_id` 契约：非空；仓内作为叶子身份唯一；稳定；无空白。

schema **不得**要求 `REQ-n`、`^[A-Z]{2,8}(-[A-Z]{1,6})?-[0-9]{2,3}$`，也不得禁止 `FN-login-retry`。

---

## Examples

```markdown
## In scope
- FN-login-retry 失败页上的「重试」且不双扣
```

```yaml
schema: overlay-trace/v1
suite: checkout-retry
items:
  - function_id: FN-login-retry
    case_id: FN-login-retry/functional
    type: functional
    level: unit
```

`examples/learning-guide/` 是已编译 fixture。不要把那里的 id 抄进 schema pattern。

---

## Performance Notes

第一刀不解析 docx。一篇 inbox 只切一块。token 只花在 generate。校验先跑 [`schema/check.py`](../../schema/check.py)。

---

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 不知道用什么 id | 先抄接入方文档已有编号。没有就铸 `FN-…`。 |
| 想改成 `LOGIN-01` 以求规范 | 不要，除非文档本来就用它。改号等于断两棵树。 |
| fixture 里看到 `ML-FR-004` | 编译结果。内核例子用 `FN-login-retry`。 |
| 想写回执或把别人的 suite 标 blocked | 停。人审才改状态。 |
| 抓不到全局 corner | 先读全部 inbox/suites，写 `invariants.yaml`。见 [`../../skills/design-cases/SKILL.md`](../../skills/design-cases/SKILL.md)。 |
| 旧 `draft` / `armed` / `reviewed_by` | `python -m overlay migrate --root .`。 |
