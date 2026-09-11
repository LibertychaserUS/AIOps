---
name: use-overlay
description: >-
  Operate Overlay — inbox, suites, validate, cover, select, run, migrate.
  Pin overlay-v2.0.0. Leaves must use ### Functional / ### Negative / ### Edge.
  Status is active|blocked. Do not generate on push. Do not use for GitHub
  Rulesets (use use-forge).
metadata:
  short-description: Overlay v2 contract and validate; active|blocked
---

# Use Overlay

Overlay turns requirement leaves into reviewable suites. CI runs only **`active`**. `blocked` drops and must not redden `overlay-check`.

Do not vendor `overlay/` into the product repo. Case method: [`../design-cases/SKILL.md`](../design-cases/SKILL.md). Contract: [`../../docs/overlay-contract.md`](../../docs/overlay-contract.md). CI: [`../../docs/overlay-ci.md`](../../docs/overlay-ci.md).

## Lock / 不绿不能合

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

- 契约 / 三技法 / invariant 点名 / blocked 不入选 / 回执 / `forbid_hosts`：`python -m overlay validate|cover|select|run` → CI **`overlay-check`**
- Overlay 测试只走 Overlay active `product_command`。Forge 单测走 **`forge-check`**。**通用检查 ≠ 产品门。** 产品门按 `forge.yaml` 的 CI job 名选跑或跳过。
- 不绿不能合。

## Contract (leaves)

`overlay validate` treats every `##` heading’s first whitespace-free token as a `function_id`. Active leaves need three `###` technique headings.

```markdown
## AUTH-01
### Functional
### Negative
### Edge
```

- Technique headings must be **`### Functional` / `### Negative` / `### Edge`**. **Do not** use `### Depth`.
- **Do not** use `## Specified` (or any prose `##`). It becomes a `function_id`.
- `function_id` is globally unique across this overlay root.
- `invariants.yaml` `function_ids` must match existing `##` titles. The invariant id must appear as a token in some `cases.md`.
- New suites default to `active` (omit `status` or set it). Park unfinished work as `blocked` with a `blocked_reason` that contains `http(s)://…` or a register id (`OF-12`, `#123`).
- Suite files use `schema: overlay-suite/v2`. Old `draft` / `armed` / `reviewed_by` → run `python -m overlay migrate --root .`.

Pin **`overlay-v2.0.0`**. Do not pin `main`. Do not force-move older tags.

## Instructions

1. Checkout the pin beside the product repo. Need CPython **3.12+**.
2. `python3 -m pip install -r <tool>/requirements.txt` and `export PYTHONPATH=<tool>`
3. Write or edit `inbox/<id>.md` and `suites/<id>/`. One slice = one id. Copy ids from adopter docs — do not invent a second numbering series.
4. Design cases against the **whole** overlay root (`$design-cases`).
5. Validate:

```text
PYTHONPATH=<tool> python3 -m overlay validate --root .
PYTHONPATH=<tool> python3 -m overlay cover --root .
PYTHONPATH=<tool> python3 -m overlay select --root .
```

`--branch` 缺省：`GITHUB_BASE_REF` → `GITHUB_REF_NAME` → `main`。未知分支回落 `branches.default` 再到 `main`。

6. `blocked` 需要带链接或登记编号的 `blocked_reason`。Agent 不要把别人的 `active` 改成 `blocked`（那是人审 / `$manage-repo`）。
7. **Keep** the product’s existing overlay-check shape if it already works (reusable caller **or** inline). Never pin `main`.

From v1:

```text
PYTHONPATH=<tool> python3 -m overlay migrate --root .
```

## Never

- Do not vendor `overlay/` / `forge/`.
- Do not replace a working overlay-check with a different shape.
- Do not generate on push.
- Do not put `status` on inbox.
- Do not copy workshop `pr-title` / `sop-lock` into a product repo’s CI unless that product is this workshop.

## Examples

```text
PYTHONPATH=<tool> python3 -m overlay validate --root .
PYTHONPATH=<tool> python3 -m overlay cover --root .
# select: blocked suites drop; overlay-check stays green
python3 -m overlay migrate --root . --dry-run
```

Reusable caller（详见 [`docs/overlay-ci.md`](../../docs/overlay-ci.md)）：

```yaml
jobs:
  overlay:
    uses: <tool-repo>/.github/workflows/overlay.yml@overlay-v2.0.0
    with:
      enable_run: true
      setup_command: pip install -r requirements-dev.txt
```

示例 fixture：`examples/learning-guide/`（示例，不是内核）。

## Performance Notes

validate / cover / select are local YAML. No model. `run` only executes `active` `product_command`. `forbid_hosts` is string match, not a security boundary.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想把 `overlay/` 拷进产品仓 | 停。`PYTHONPATH=<tool>`。 |
| `### Depth` / `## Specified` | 契约红。改成 `### Edge`；Specified 改成段落。 |
| 跨套件重复 `function_id` | 契约红。全局唯一。 |
| invariant 点了不存在的 `##` | 契约红。先对齐标题。 |
| `status: draft` / `armed` / `reviewed_by` | 契约红。`python -m overlay migrate --root .`。 |
| blocked 缺链接 | 契约红。`blocked_reason` 写 `https://…` 或 `OF-12` / `#123`。 |
| 想 pin `main` | 停。pin `overlay-v2.0.0`。 |
| 想把 overlay-check 改成另一种形状 | 停。已有 reusable + wrapper 或 inline，不要换。 |
