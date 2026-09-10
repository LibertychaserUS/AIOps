# AIOps

Workshop for two reusable GitHub products. Not the empty First-Light `AIOps` repo. Learning Guide is the first fixture, not the product.

| Product | Job |
|---|---|
| **Forge** | Make multi-person (and agent) GitHub work ordered: PR-only, reviewed, no direct push to protected branches |
| **Overlay** | Generate reviewable tests; run only `armed` suites. Does not replace a repo’s existing build gate |

Neither deploys. Neither attaches Proctor. Neither edits Learning Guide Verify.

Overlay is a standard part: it freezes **contract fields**, not a product’s numbers, PRD chapter tree, IEEE filenames, or test folder layout. Agents read adopter docs and compile them into `inbox/` + `suites/`.

This workshop uses Overlay on itself: `overlay.yaml`, `inbox/`, `suites/`, and `.github/workflows/overlay-check.yml` (validate + select + run armed `product_command`). Learning Guide remains a fixture under `examples/learning-guide/`.

Status: Forge first slice is `python -m forge apply --dry-run` (no live apply). Overlay is `validate` / `select` / `run` / `cover` + receipt. Test and CI are the same gate. Case cover = leaf triad + declared invariants, not PRD-wide or line coverage. No `generate` yet.

- **完整详细设计：** [`docs/design.md`](docs/design.md)
- Inbox 输入面：[`docs/inbox.md`](docs/inbox.md)
- 测试体系规格（两棵树 + 接入方自选 `function_id`）：[`docs/test-spec.md`](docs/test-spec.md)
- **使用 SOP / skill：** [`skills/use-forge/SKILL.md`](skills/use-forge/SKILL.md)、[`skills/use-overlay/SKILL.md`](skills/use-overlay/SKILL.md)、[`docs/sop.md`](docs/sop.md)
- **接到其他项目：** 工具留在本仓或你的 **fork**。不要把 `forge/`、`overlay/`、`schema/`、`prompts/` 提交进产品仓。产品仓只留薄配置 + `inbox/` / `suites/` + 一条 `uses:` 工具仓 reusable workflow（pin tag/SHA）。步骤见 [`docs/products.md`](docs/products.md) 与两条 skill。
- Agent skill（IEEE 子集）：[`docs/agents/ieee-test-system.md`](docs/agents/ieee-test-system.md)
- Agent：读文档编成契约 [`docs/agents/overlay-contract.md`](docs/agents/overlay-contract.md)；用例设计 / 覆盖 [`docs/agents/case-design.md`](docs/agents/case-design.md)；IEEE 剖面 [`docs/agents/ieee-test-system.md`](docs/agents/ieee-test-system.md)
- 产品怎么接到别的仓：[`docs/products.md`](docs/products.md)
- 约束：[`docs/2026-09-10-对话整理.md`](docs/2026-09-10-对话整理.md)
- Overlay 契约：[`schema/suite.schema.json`](schema/suite.schema.json)、[`schema/inbox.schema.json`](schema/inbox.schema.json)、[`schema/trace.schema.json`](schema/trace.schema.json)、[`schema/receipt.example.yaml`](schema/receipt.example.yaml)
- LG fixture（已编译例）：[`examples/learning-guide/`](examples/learning-guide/)
- Forge 政策：[`forge/agent-policy.md`](forge/agent-policy.md)、[`forge/ruleset.protected-default.json`](forge/ruleset.protected-default.json)
