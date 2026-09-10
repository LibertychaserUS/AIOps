---
name: use-overlay
description: >-
  SOP for using Overlay: write inbox, validate, select armed suites, run
  their product_command in CI. Test and CI are the same gate. Use when
  adopting Overlay, writing inbox/suites, running overlay validate/select/run,
  or wiring overlay-check. Do not use for GitHub Rulesets (use use-forge).
  Do not generate or arm without a human.
---

# Use Overlay

Overlay is a standard part. Freeze the contract, not a product’s numbers. Agents **read adopter docs and compile** them into `inbox/` + `suites/`. Detailed compile rules: [`docs/agents/overlay-contract.md`](../../docs/agents/overlay-contract.md). IEEE subset: [`docs/agents/ieee-test-system.md`](../../docs/agents/ieee-test-system.md).

**Test and CI are one chain.** `suites/<id>/` is the test spec. `product_command` is what CI runs after `select` keeps only `armed`. There is no second test job beside Overlay.

## Instructions

### Humans / agents — write

1. **One slice = one inbox.** `inbox/<id>.md` (front matter + short Markdown). Same `id` as `suites/<id>/` after compile. Do not vendor a whole PRD.
2. **Read the adopter docs**, then compile. `function_id` is whatever stable, unique, non-whitespace string the docs already use. Do not invent a second numbering system for unit / e2e / k6. The same id is what CI receipts point at when a command fails.
3. **Validate locally** (no model):
   ```text
   python -m overlay validate --root .
   ```
4. **`generate` is not on this path.** Do not run it on push. When it exists: human or `workflow_dispatch` only; output `status: draft`; never write `reviewed_by` or `armed`. Until then, hand-write `suites/<id>/`.
5. **Humans arm or block.** Edit `suite.yaml` only. `blocked` = reviewed, not ready to gate. `armed` = reviewed and claimed testable. Agents must not arm. An `armed` suite that should gate CI needs a `product_command`. Missing command is skip, not red.

### CI — same gate as the tests

6. Wire reusable [`.github/workflows/overlay.yml`](../../.github/workflows/overlay.yml). This workshop’s `overlay-check.yml` uses `enable_run: true` and pins `branch: main` so agent branches still run the armed tool tests.
7. Push / PR runs **validate + select + run**. `run` executes each selected suite’s `product_command` in the **caller checkout**. It does not clone a foreign product repo (Learning Guide Portal is never checked out from here). No generate. No token spend.
8. Local equivalent:
   ```text
   python -m overlay select --branch main --root . --write-receipt receipts/
   python -m overlay run --branch main --root . --workdir . --write-receipt receipts-run/
   ```
   Only `armed` suites whose `kind` is in `overlay.yaml` for that branch. `draft` / `blocked` drop and must not redden the job. Unknown branch → empty set, still green. Failed armed command → exit 5 (job red). Command hitting `forbid_hosts` → exit 2, command not started.
9. Receipts are program-written (`wrote_by: select` or `wrote_by: run`). Models must not write them. `run` without `--write-receipt` is no evidence (exit 2).

### Never

- Do not replace or `workflow_call` the adopter’s existing build workflow (Learning Guide Verify is the first example).
- Do not attach Proctor. Do not hit production hosts in `forbid_hosts`.
- Do not put `status` / `reviewed_by` on inbox.
- Do not keep a second unit-test workflow that bypasses Overlay select. If a test should gate, it is an armed `product_command`.

## Examples

This workshop (already adopted):

```text
python -m overlay validate --root .
python -m overlay select --branch main --root .
# selected: forge-apply, overlay-select
# dropped: overlay-generate (blocked)
python -m overlay run --branch main --root . --workdir . --write-receipt receipts-run/
# forge-apply → forge unit tests + apply --dry-run
# overlay-select → schema/check.py + overlay unit tests
```

Learning Guide is a **fixture** under `examples/learning-guide/`, not the Overlay kernel. Its armed suite has no `product_command` (skip, not red). This workshop must not checkout `LearningGuidePortal`.

## Performance Notes

validate / select are local YAML. `run` is local subprocess in the caller checkout. Token only on explicit generate (not shipped). Do not parse docx on this path.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| validate 退出 2 | 契约红。读打印的路径。不是业务功能红。 |
| blocked 把 check 染红 | bug。blocked 必须丢弃。 |
| armed 命令失败退出 5 | 修那个 `function_id` 对应的代码或命令。回执里有 `ran` + `exit_code`。 |
| 命令命中 forbid_hosts | 契约红（退出 2）。改命令，不要打生产域。 |
| 想在 inbox 写 Playwright | 停。inbox 是输入；用例在 `cases.md`；CI 跑的是 `product_command`。 |
| 不知道 function_id | 抄接入方文档已有编号；没有就铸。不要改成“更像 IEEE”的另一套号。 |
| 想 push 时 generate | 停。人点或 dispatch。 |
| 想自动 armed | 停。人改 `suite.yaml`。 |
| 另开一个 unittest workflow | 停。把命令写进 armed suite。 |
