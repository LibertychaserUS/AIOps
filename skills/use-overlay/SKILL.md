---
name: use-overlay
description: >-
  SOP for using Overlay: write inbox, validate, select armed suites, preview
  CI. Use when adopting Overlay, writing inbox/suites, running overlay
  validate/select, or wiring overlay-check. Do not use for GitHub Rulesets
  (use use-forge). Do not generate or arm without a human.
---

# Use Overlay

Overlay is a standard part. Freeze the contract, not a product’s numbers. Agents **read adopter docs and compile** them into `inbox/` + `suites/`. Detailed compile rules: [`docs/agents/overlay-contract.md`](../../docs/agents/overlay-contract.md). IEEE subset: [`docs/agents/ieee-test-system.md`](../../docs/agents/ieee-test-system.md).

## Instructions

### Humans / agents — write

1. **One slice = one inbox.** `inbox/<id>.md` (front matter + short Markdown). Same `id` as `suites/<id>/` after compile. Do not vendor a whole PRD.
2. **Read the adopter docs**, then compile. `function_id` is whatever stable, unique, non-whitespace string the docs already use. Do not invent a second numbering system for unit / e2e / k6.
3. **Validate locally** (no model):
   ```text
   python -m overlay validate --root .
   ```
4. **`generate` is slice 2.** Do not run it on push. When it exists: human or `workflow_dispatch` only; output `status: draft`; never write `reviewed_by` or `armed`. Until then, hand-write `suites/<id>/`.
5. **Humans arm or block.** Edit `suite.yaml` only. `blocked` = reviewed, not ready to gate. `armed` = reviewed and claimed testable. Agents must not arm.

### CI — preview

6. Wire reusable [`.github/workflows/overlay.yml`](../../.github/workflows/overlay.yml) with `enable_run: false`. Example: this workshop’s `overlay-check.yml`.
7. Push / PR runs **validate + select only**. No product checkout. No token. `run` stays skipped.
8. Select:
   ```text
   python -m overlay select --branch main --root . --write-receipt receipts/
   ```
   Only `armed` suites whose `kind` is in `overlay.yaml` for that branch. `draft` / `blocked` drop and must not redden the job. Unknown branch → empty set, still green.
9. Receipt is program-written (`wrote_by: select`). Models must not write it.

### Never

- Do not replace or `workflow_call` the adopter’s existing build workflow (Learning Guide Verify is the first example).
- Do not attach Proctor. Do not hit production hosts in `forbid_hosts`.
- Do not put `status` / `reviewed_by` on inbox.

## Examples

This workshop (already adopted):

```text
python -m overlay validate --root .
python -m overlay select --branch main --root .
# selected: forge-apply, overlay-select
# dropped: overlay-generate (blocked)
```

Learning Guide is a **fixture** under `examples/learning-guide/`, not the Overlay kernel.

## Performance Notes

validate / select are local YAML. Token only on explicit generate (not shipped). First slice does not parse docx.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| validate 退出 2 | 契约红。读打印的路径。不是业务功能红。 |
| blocked 把 check 染红 | bug。blocked 必须丢弃。 |
| 想在 inbox 写 Playwright | 停。inbox 是输入；用例在 `cases.md`。 |
| 不知道 function_id | 抄接入方文档已有编号；没有就铸。不要改成“更像 IEEE”的另一套号。 |
| 想 push 时 generate | 停。人点或 dispatch。 |
| 想自动 armed | 停。人改 `suite.yaml`。 |
