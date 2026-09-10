---
name: use-overlay
description: Operate Overlay (inbox, suites, validate, select, run, cover) without vendoring the tool into a product repo. This skill should be used when adopting Overlay, writing inbox or suites, covering corner cases, running overlay validate/select/run/cover, or wiring overlay-check. Do not use for GitHub Rulesets (use use-forge). Do not generate or arm without a human.
metadata:
  short-description: Adopt Overlay without vendoring the tool
---

# Use Overlay

Overlay is a standard part. Freeze the contract, not a product’s numbers. Agents **read adopter docs and compile** them into `inbox/` + `suites/`. Detailed compile rules: [`docs/agents/overlay-contract.md`](../../docs/agents/overlay-contract.md). IEEE subset: [`docs/agents/ieee-test-system.md`](../../docs/agents/ieee-test-system.md). Case design: [`../design-cases/SKILL.md`](../design-cases/SKILL.md).

**Overlay test and Overlay CI are one chain.** `suites/<id>/` is the test spec. `product_command` is what Overlay CI runs after `select` keeps only `armed`. There is no second Overlay test job beside Overlay. Forge tests do not ride Overlay run.

**Who reviews and merges code:** GitHub humans + Ruleset ([`docs/rbac.md`](../../docs/rbac.md)). Overlay only decides which suites run. **管理端** arms/blocks and writes `reviewed_by`: [`../manage-repo/SKILL.md`](../manage-repo/SKILL.md). **开发端** writes inbox/suites as draft and fixes armed-red: [`../dev-pr/SKILL.md`](../dev-pr/SKILL.md). Agents never arm.

## Lock / 不绿不能合

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集，不 NLP 扫散文。

- Overlay Ops PR 链：规格 → CodeRabbit/Copilot 评论 → 本分支全量 Overlay CI → 人合。失败打回并留 `ops-debug`：`overlay-check.yml` + `python -m forge ops-review` / `bounce` → **`overlay-check`**
- 契约 / 三技法 / invariant 点名 / blocked 不入选 / 回执 / `forbid_hosts`：`python -m overlay validate|cover|select|run` → CI **`overlay-check`**
- push 不 generate、不 checkout LearningGuidePortal、不 `workflow_call` 产品 Verify、不另开 `self-test` 绕过 Overlay select：`python -m forge sop-lock` → CI **`sop-lock`**
- Overlay 测试只走 Overlay armed `product_command`。Forge 单测走 **`forge-check`**。`sop-lock` 不是 Overlay 旁路 unittest。**通用检查 ≠ 产品门。** 产品门按 `forge.yaml` `ci` 选跑或跳过。
- 不绿不能合。人审：用例写得好不好、`reviewed_by` 是不是人。

## Instructions

### Reuse — keep the tool out of the product commit repo

Do not upload or vendor the tool into the adopter's product git repo (the repo they commit and push). 不要把工具上传到接入方要提交、推送的产品仓。

| Keep here | Never `git add` into the product tree |
|---|---|
| This workshop `LibertychaserUS/AIOps`, **or** the adopter's **fork** of this workshop | `overlay/`, `forge/`, `schema/`, `prompts/`, this workshop's Python packages |

The product repo commits **only**:

- `overlay.yaml`
- `inbox/`
- `suites/`
- `invariants.yaml` (optional)
- a thin workflow that `uses:` [`.github/workflows/overlay.yml`](../../.github/workflows/overlay.yml) from the **tool** repo — pin a **tag or commit SHA**, not floating `main`

That is the whole adoption surface. Do **not** copy `overlay/` into the product tree so that CI sees `local=true`. When `overlay/__init__.py` is absent, the reusable workflow checkouts `LibertychaserUS/AIOps` into `_aiops` and sets `PYTHONPATH`. **That checkout is the correct reuse path.**

Local CLI: checkout the tool repo or fork **beside** the product. Set `PYTHONPATH`. Do not `git add` the tool tree.

```text
# sibling checkouts — product git must not contain overlay/
../AIOps/          # LibertychaserUS/AIOps or your fork
./my-product/      # overlay.yaml + inbox/ + suites/ only

cd my-product
PYTHONPATH=../AIOps python3 -m overlay validate --root .
PYTHONPATH=../AIOps python3 -m overlay cover --root .
```

If you forked the workshop, `uses:` **your fork** at a pin. A fork that diverges from upstream should point the workflow's tool checkout at that fork (the default in this workshop checkouts `LibertychaserUS/AIOps`). Never pin floating `main`.

### Humans / agents — write

1. **One slice = one inbox.** `inbox/<id>.md` (front matter + short Markdown). Same `id` as `suites/<id>/` after compile. Do not vendor a whole PRD. Developers land this through a PR (`$dev-pr`).
2. **Read the adopter docs**, then compile. `function_id` is whatever stable, unique, non-whitespace string the docs already use. Do not invent a second numbering system for unit / e2e / k6. The same id is what CI receipts point at when a command fails. Do not couple the kernel to one product's routes, domains, or numbering.
3. **Design cases against the whole overlay root**, not one inbox. Method: [`../design-cases/SKILL.md`](../design-cases/SKILL.md) (linked notes: [`docs/agents/case-design.md`](../../docs/agents/case-design.md)). `armed` needs Functional / Negative / Edge. Global corners go in `invariants.yaml` and must be cited in some `cases.md`. Coupled leaves get `span: interaction` + `relates` — no `CROSS-01` series, no pairwise explosion.
4. **Validate and print cover** (no model). Use `PYTHONPATH` to the tool checkout when you are not inside this workshop:
   ```text
   PYTHONPATH=../AIOps python3 -m overlay validate --root .
   PYTHONPATH=../AIOps python3 -m overlay cover --root .
   ```
5. **`generate` is not on this path.** Do not run it on push. When it exists: human or `workflow_dispatch` only; output `status: draft`; never write `reviewed_by` or `armed`. Until then, hand-write `suites/<id>/`. Token only on explicit generate.
6. **Humans arm or block** (`$manage-repo`). Edit `suite.yaml` only. `blocked` = reviewed, not ready to gate. `armed` = reviewed and claimed testable. Agents must not arm. Models must not write `reviewed_by` or receipts. CI must not auto-arm. `overlay review --i-am` still refuses writes this slice — 管理端手改 yaml. An `armed` suite that should gate CI needs a `product_command`. Missing command is skip, not red.

### CI — same gate as the tests

7. Wire a **thin** caller that `uses:` the reusable overlay workflow from the tool repo (pin tag/SHA). This workshop’s `overlay-check.yml` uses `enable_run: true` and pins `branch: main` so agent branches still run the armed **tool** tests — that file is for this workshop, not something to copy the Python package from.
8. Push runs **validate + select + run**. On **pull_request** (when selected) Overlay Ops is: **spec (`pr-title`) → review-bots (CodeRabbit + Copilot comments, advisory) → full Overlay CI on this checkout → human merge**. Red spec/CI: `python -m forge bounce` 打回 the PR and keeps `overlay-ops-debug` + receipts. `run` executes each selected suite’s `product_command` in the **caller (product) checkout**. It does not clone a foreign product repo (Learning Guide Portal is never checked out from here). It **does** checkout the tool repo when `overlay/` is not local. No generate. No token spend on push. Do not wait for CodeRabbit to be a required check.
9. Local equivalent (tool next door):
   ```text
   PYTHONPATH=../AIOps python3 -m overlay select --branch main --root . --write-receipt receipts/
   PYTHONPATH=../AIOps python3 -m overlay run --branch main --root . --workdir . --write-receipt receipts-run/
   ```
   Only `armed` suites whose `kind` is in `overlay.yaml` for that branch. `draft` / `blocked` drop and must not redden the job. Unknown branch → empty set, still green. Failed armed command → exit 5 (job red). Command hitting `forbid_hosts` → exit 2, command not started.
10. Receipts are program-written (`wrote_by: select` or `wrote_by: run`). Models must not write them. `run` without `--write-receipt` is no evidence (exit 2).

### Never

- Do not vendor `overlay/` / `forge/` / `schema/` / `prompts/` into the product commit repo.
- Do not replace or `workflow_call` the adopter’s existing build workflow (Learning Guide Verify is the first example). Never change LearningGuidePortal Verify.
- Do not apply Overlay live onto Learning Guide Portal from this workshop. Do not checkout `LearningGuidePortal`.
- Do not attach / run / gate intern-workspace Proctor. Do not edit Deepseek3.
- Do not hit production hosts in `forbid_hosts` (LG: `ilovelearningguide.com`). No CD.
- Do not put `status` / `reviewed_by` on inbox.
- Do not generate on push. Do not arm as an agent. CI does not auto-arm.
- Do not keep a `self-test` workflow that bypasses Overlay select. Overlay tests that should gate Overlay CI are an Overlay armed `product_command`. Forge tests live on `forge-check`.
- Two products stay independent: Overlay does not install Rulesets; Forge does not arm suites. Overlay does not decide who may merge. Overlay run does not execute Forge submit.
- Do not build an admin Web or a second RBAC database. See [`docs/rbac.md`](../../docs/rbac.md).

## Examples

This workshop (already adopted; it **is** the tool repo, so local `overlay/` is correct **here only**):

```text
python3 -m overlay validate --root .
python3 -m overlay select --branch main --root .
# selected: overlay-select
# dropped: overlay-generate, forge-apply (blocked)
python3 -m overlay cover --root .
python3 -m overlay run --branch main --root . --workdir . --write-receipt receipts-run/
# overlay-select → schema/check.py + overlay cover + overlay unit tests
# forge-apply is not selected; forge-check runs Forge tests
```

Another product — thin caller only, pin a tag or SHA (not `main`):

```yaml
# .github/workflows/overlay-check.yml  — in the PRODUCT repo
name: overlay-check
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  overlay:
    uses: LibertychaserUS/AIOps/.github/workflows/overlay.yml@<tag-or-sha>
    with:
      enable_run: true
      root: "."
```

Learning Guide is a **fixture** under `examples/learning-guide/`, not the Overlay kernel. Its armed suite has no `product_command` (skip, not red). This workshop must not checkout `LearningGuidePortal`. Never apply live to that product.

## Performance Notes

validate / select are local YAML. `run` is local subprocess in the caller checkout. Token only on explicit generate (not shipped). Do not parse docx on this path. Adopter CI checkouts the tool repo once per job when `overlay/` is absent — that is cheaper and safer than vendoring.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想把 `overlay/` 拷进产品仓好过 CI | 停。让 `local=false`，reusable workflow 会 checkout `LibertychaserUS/AIOps`。 |
| validate 找不到 `overlay` 模块 | 本地设 `PYTHONPATH` 指向工作本或 fork；不要 `git add overlay/`。 |
| validate 退出 2 | 契约红。读打印的路径。不是业务功能红。 |
| blocked 把 check 染红 | bug。blocked 必须丢弃。 |
| armed 命令失败退出 5 | 修那个 `function_id` 对应的代码或命令。回执里有 `ran` + `exit_code`。 |
| 命令命中 forbid_hosts | 契约红（退出 2）。改命令，不要打生产域。 |
| 想在 inbox 写 Playwright | 停。inbox 是输入；用例在 `cases.md`；CI 跑的是 `product_command`。 |
| 不知道 function_id | 抄接入方文档已有编号；没有就铸。不要改成“更像 IEEE”的另一套号。 |
| 想 push 时 generate | 停。人点或 dispatch。 |
| 想自动 armed | 停。人改 `suite.yaml`（`$manage-repo`；`review` CLI 这一刀不写盘）。 |
| 谁来 merge 这个 PR | GitHub 人 + Ruleset，不是 Overlay。`$manage-repo` / [`docs/rbac.md`](../../docs/rbac.md)。 |
| 另开一个 Overlay unittest workflow / 让 Overlay run 跑 Forge 单测 | 停。Overlay 命令写进 Overlay armed suite。Forge 单测走 `forge-check`。 |
| 抓不到全局 corner | 先读全部 inbox/suites，把性质写成 invariant，再写叶子。不要两两穷尽。见 `$design-cases`。 |
| armed 缺 Edge | 契约红。补技法。 |
| `uses: …@main` | 停。pin tag 或 SHA。 |
