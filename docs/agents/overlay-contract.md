# Overlay 契约：读文档，编成 schema

给人和 agent 的技能说明。IEEE 剖面与两棵树见 [`ieee-test-system.md`](ieee-test-system.md)。对照：[`../test-spec.md`](../test-spec.md)、[`../inbox.md`](../inbox.md)、[`../design.md`](../design.md) §4、[`../../schema/`](../../schema/)。

**不是**某一家产品的技能。Learning Guide 的 id 只许出现在 fixture，不许写进 Overlay 源码或 schema 的合法清单。

---

## Instructions

1. **先读接入方文档**，不要先发明目录。读 PRD、设计、inbox、已有测试里人家已经写的 id。不要改 LearningGuidePortal Verify，不要 attach Proctor，不要打生产域名。
2. **编成契约形状**，不要重排对方的树：
   - 一篇切片 → `inbox/<id>.md`
   - 一次 generate → `suites/<id>/suite.yaml` + `cases.md` + 可选 `trace.yaml`
   - 叶子身份 → `function_id`（语法见下）
3. **`function_id` 产品无关语法：** `^[A-Z]{2,8}(-[A-Z]{1,6})?-[0-9]{2,3}$`。PRD 已有且符合语法就抄。没有就铸造 `LOGIN-01` 这种号，写入 In scope 行首，此后稳定。不要 `REQ-n`，不要 `E2E-B1` / `UT-007` / `FN-login-retry`。
4. **两棵树只对齐叶子。** 文档树和测试树形状不同。对上的叶子共用同一个 `function_id`。unit / integration / smoke / k6 / e2e 是 `level` 面。
5. **IEEE 只取剖面。** identification、levels、trace。不要交二十份 Word。
6. **`generate` 只编译。** 读 inbox，吐出契约合法文件，`status` 必须是 `draft`。禁止在源码里写死一张产品 FR 表。
7. **不要越权。** 不写 `reviewed_by`、不写回执、不把 `status` 改成 `armed`、不改接入方构建 workflow。

---

## Examples

内核 / 设计例（通用号，不是某产品目录）：

```markdown
## In scope
- LOGIN-01 失败页上的「重试」且不双扣
- CHK-02 幂等键已存在时不新建支付
```

```markdown
## LOGIN-01 失败页上的「重试」且不双扣
```

```yaml
schema: overlay-trace/v1
suite: checkout-retry
items:
  - function_id: LOGIN-01
    case_id: LOGIN-01/unit/01
    type: functional
    level: unit
  - function_id: LOGIN-01
    case_id: LOGIN-01/e2e/01
    type: functional
    level: e2e
```

`examples/learning-guide/` 是已编译 fixture，那里可以出现 `ML-FR-004` / `PAY-01` / `AUTH-01`。不要把那些 id 抄进 `overlay/` 源码当合法清单。

反例：

- 在 schema 里要求 `^REQ-[0-9]+$`
- 看见 PRD 第七章就在 overlay 仓建第七章目录
- generate 内置一张产品 FR 表再对号
- 为 IEEE 829 创建 `MasterTestPlan.docx`
- 用 `E2E-B1` 或 `LOAD-001` 当主键（level 用 `/e2e/`、`/k6/`）

---

## Performance Notes

- 第一刀不解析 docx / 不拉 Figma。人把摘录和 id 放进 inbox。
- 一篇 inbox 只切一块。宁多篇短的。
- token 只花在 `generate`。push 路径不调模型。
- 校验先跑 [`schema/check.py`](../../schema/check.py)。

---

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 不知道用什么 id | 先在接入方文档里找已有、且符合语法的编号。没有就铸 `LOGIN-01` 风格，写进 inbox。 |
| 想把 id 改成 `REQ-1` | 不要。改号等于断两棵树。 |
| fixture 里看到 `ML-FR-004` | 那是编译结果。内核例子继续用 `LOGIN-01`。 |
| 想写 `reviewed_by` 或 `armed` | 停。人审才写。 |
| 产品仓测试目录和 PRD 目录对不上 | 预期如此。只在映射叶子上放同一 `function_id`。 |
| 需要 IEEE 测试计划正文 | 读接入方已有计划，把 identification / levels / trace 编进 suite。 |
