---
name: design-cases
description: >-
  Design Overlay cases — leaf triad Functional / Negative / Edge plus declared
  invariants. Use when writing cases.md or invariants.yaml or running overlay
  cover. Not line coverage. Use with use-overlay. Do not use ### Depth or
  ## Specified.
metadata:
  short-description: Overlay triad, invariants, unique function_id
---

# Design Cases

Define Overlay “full cover” before writing any `cases.md`. Operate Overlay with [`../use-overlay/SKILL.md`](../use-overlay/SKILL.md). Contract: [`../../docs/overlay-contract.md`](../../docs/overlay-contract.md).

## Lock / 不绿不能合

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

- active 缺技法、invariant 未点名：`python -m overlay validate` / `cover` → CI **`overlay-check`**
- 不 NLP 判断「角想全了没有」。人看 `cover` 矩阵再决定 `blocked` / `active`。
- 仓级禁令（push 不 generate）见 `python -m forge sop-lock` → **`sop-lock`**。

## Instructions

Full cover is three layers — not PRD scan, not line coverage, not N×N leaves:

| Layer | What is standard |
|---|---|
| Leaf techniques | Each `function_id` has Functional / Negative / Edge |
| Invariants | Each declared invariant is cited in some `cases.md` |
| Interaction | Only when leaves are already coupled (`span: interaction` + `relates`) |

Write any `cases.md` only after reading the whole overlay root: all `inbox/*.md`, all `suites/*/cases.md`, `invariants.yaml`, and “不得 / 永不” sentences in the product docs.

`active` 缺技法 → `validate` / `cover` 契约红。`blocked` 可以薄，cover 只提示。

### 1. Inventory

List existing `function_id`s. Copy them from adopter docs. Do not invent `E2E-B1` / `CROSS-01` / `REQ-n`.

### 2. Leaf triad

Each `function_id` is a `## <id>` section. The three `###` titles must be these words (case-insensitive):

```markdown
## AUTH-01
### Functional
### Negative
### Edge
```

**Do not** write `### Depth`. **Do not** write `## Specified / not tested now`. `function_id` is globally unique. `invariants.yaml` `function_ids` must match existing `##` titles.

### 3. Invariants

Typical sources (only visible after reading the whole tree):

- 状态机：`blocked` 永不把 overlay-check 染红
- 跨产品：Forge 不把 Overlay `status` 改成 `blocked`（agent 分支）
- 安全：不打 `forbid_hosts`；push 不 `generate`
- 账本：回执只能 `select` / `run` 写

Each declared invariant must appear as a token in some `cases.md`. Do not point an invariant at a `##` title that does not exist.

### 4. Interaction only when coupled

Shared session / entitlement / “不得同时” → one case on the leaf that fails first, plus `span: interaction` and `relates`. No pairwise explosion.

### 5. Human review

`cover` prints the matrix. Humans decide `blocked` / `active`. Models do not flip other people’s suites to `blocked`.

## Never

- Do not generate on push.
- Do not vendor `forge/` / `overlay/`.
- Do not use `### Depth` or `## Specified`.

## Examples

```text
PYTHONPATH=<tool> python3 -m overlay cover --root .
```

A suite can have a full triad and still be `blocked`: design is done, the gate does not run.

## Performance Notes

`cover` / `validate` only scan this repo’s YAML and Markdown.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| active 缺 Edge | 补 `### Edge`，不要用 `### Depth`，不要改成 blocked 躲。 |
| 写了 `## Specified` | 改成段落。 |
| 跨套件重复 function_id | 换一个稳定唯一的 id。 |
| invariant 点了不存在的 `##` | 先对齐标题。 |
| 想两两组合所有叶子 | 停。没有耦合就不是测试项。 |
| 旧 `draft` / `armed` | `python -m overlay migrate --root .`。 |
