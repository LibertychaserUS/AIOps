# Overlay 测试体系 skill（IEEE 子集）

Agent 读本文 + [`../test-spec.md`](../test-spec.md)。编译步骤见 [`overlay-contract.md`](overlay-contract.md)。不要另写「测试规格说明书」，不要搬 IEEE 二十份文档。

本仓没有名为 “IEEE skill” 的旧文件。本页就是 agent 要跟的 profile：IEEE 829 / ISO/IEC/IEEE 29119 的 **识别、层次、双向追溯**。

---

## 两棵树

产品文档是一棵树。测试体系是另一棵树。枝叶形状不同，必须用同一 `function_id` 对齐。

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

对齐是 **map**，不是 clone。

| 规则 | 含义 |
|---|---|
| 一篇 PRD 章节 | 可以对应 0..n 个 test item |
| 一个 test item | 恰好属于一个 `function_id` |
| 一个 `function_id` | 可以有 0..n 个 level |
| 失败时 | receipt / `cases.md` / 文件名必须带 `function_id`，才能指回 PRD 叶子 |

Suite 目录名（`suites/checkout-retry/`）是 inbox 切片容器，**不是** `function_id`。

---

## `function_id`

产品无关语法（内核契约，不是某家产品的号段）：

```text
^[A-Z]{2,8}(-[A-Z]{1,6})?-[0-9]{2,3}$
```

合法：`LOGIN-01`、`CHK-02`、`PAY-01`、`AUTH-01`、`LEARN-02`、`KS-01`、`ML-FR-004`。  
不合法当主键：`E2E-B1`、`UT-007`、`REQ-1`、`FN-login-retry`。  
可选实例：`<function_id>/<level>/<seq>`，例如 `LOGIN-01/unit/01`。

| 做 | 不做 |
|---|---|
| 和 PRD 功能用同一个 id | 再发明 `E2E-B1`、`UT-007`、`LOAD-001` 第二套编号 |
| inbox In scope 行首带上或铸造该 id | 用 inbox 本地 `REQ-n` 当标题 id |
| generate 把该 id 抄进 `cases.md` 二级标题 | 把 level 做成另一套号段 |
| 人审后 id 保持稳定 | 换文件名就换 id |

PRD 已有编号且符合语法：inbox **抄**它。PRD 没有编号：这篇 inbox 是登记处，**铸造一次**，之后不再改。内核例子用 `LOGIN-01`，不要把某产品 FR 清单写进 schema。

`functional` / `negative` / `edge` 是 IEEE 测试技法（`trace.yaml` 的 `type`），不是第三套 id。

---

## IEEE 子集（采用的词）

来自 IEEE 829 与 ISO/IEC/IEEE 29119-1/2/3。29119-3:2021 把部分 “test condition” 说成 test model；本仓仍用下面六个名字。

| 词 | 本仓落点 |
|---|---|
| **test item** | 一个 `function_id`：被测的那条产品功能 |
| **test condition** | 这条功能要行使的条件（inbox In scope / 技法小节） |
| **test case** | 一组输入、执行条件、期望（`cases.md` 一条） |
| **test procedure** | 步骤（Steps） |
| **test level** | `unit` \| `integration` \| `smoke` \| `k6` \| `e2e`（同一 id 的面） |
| **requirements traceability** | `trace.yaml`：PRD 功能 ↔ test item ↔ case；双向 |

不采用：Master/Level Test Plan、环境规格、异常报告、二十份 Word 模板、按 PRD 章节镜像的第二本规格书。

---

## 失败怎么指回 PRD

1. 打开失败的 case / receipt 事件，读 `function_id`。
2. 用同一 id 打开产品 PRD / design / FR 叶子。
3. 用 `level` 判断是哪一层断了。
4. 不要先猜 suite 目录名或 `E2E-B*` 故事号。

---

## Learning Guide fixture（只举例，不是 Overlay 内核）

复用产品仓已有编号：`ML-FR-004`、`ML-FR-007`、`PAY-01`、`AUTH-01`、`LEARN-02`、`KS-01`。  
反例：`E2E-B1` 当独立号族；`k6` 的 `LOAD-001` 除非映射到某个 PRD 功能（付款负载应是 `PAY-01/k6/01`）。

完整表见 [`../test-spec.md`](../test-spec.md) §13。
