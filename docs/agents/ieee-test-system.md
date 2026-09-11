# Overlay 测试体系：IEEE 当作剖面

Agent 先读 [`overlay-contract.md`](overlay-contract.md)，再读本文 + [`../test-spec.md`](../test-spec.md)。

本文只解释 IEEE 829 / ISO/IEC/IEEE 29119 的 **识别、层次、追溯**，不是产品编号表，也不是二十份 Word。

---

## 两棵树

产品文档是一棵树。测试体系是另一棵树。形状由接入方文档决定。对上的叶子共用同一个接入方自选的 `function_id`。

```text
接入方文档树                         接入方测试树
        │                                        │
        └──────────── FN-login-retry ────────────┘
```

对齐是 map，不是 clone。level 是面，不是第二套号。suite 目录名不是 `function_id`。

---

## `function_id`（契约，不是号段法律）

非空；仓内作为叶子身份唯一；稳定；无空白。接入方选字符串。

schema **不得**要求 `REQ-n`、`LOGIN-01`、`ML-FR-004`，或 `^[A-Z]{2,8}(-[A-Z]{1,6})?-[0-9]{2,3}$`。

不要发明 `E2E-B1` / `UT-007` 当第二套主键。`type` 是技法，不是第三套 id。

---

## IEEE 子集

| 词 | 本仓 |
|---|---|
| test item | 一个 `function_id` |
| test condition | inbox In scope / 技法小节 |
| test case | `cases.md` 一条 |
| test procedure | Steps |
| test level | unit / integration / smoke / k6 / e2e（可选） |
| requirements traceability | `trace.yaml`（可选 `span` / `relates`） |
| 系统性质 | `invariants.yaml`：跨叶子必须为真的性质，不是第四套主键 |

不采用 Master/Level Test Plan、二十份 Word、按 PRD 章节镜像的规格书。

全局边角：先读整棵测试树，再声明 invariant。不要用新号族。方法：[`../../skills/design-cases/SKILL.md`](../../skills/design-cases/SKILL.md)（旧入口 [`case-design.md`](case-design.md)）。

失败时读 `function_id`，指回文档叶子；用 `level` 看是哪一层。

`examples/` 里可以出现某产品自己的 id。那些不是 Overlay 合法编号表。内核例子用 `FN-login-retry`。
