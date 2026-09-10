# AIOps

Workshop for two reusable GitHub products. Not the empty First-Light `AIOps` repo. Learning Guide is the first fixture, not the product.

| Product | Job |
|---|---|
| **Forge** | Make multi-person (and agent) GitHub work ordered: PR-only, reviewed, no direct push to protected branches |
| **Overlay** | Generate reviewable tests; run only `armed` suites. Does not replace a repo’s existing build gate |

Neither deploys. Neither attaches Proctor. Neither edits Learning Guide Verify.

Overlay is a standard part: it freezes **contract fields**, not a product’s numbers, PRD chapter tree, IEEE filenames, or test folder layout. Agents read adopter docs and compile them into `inbox/` + `suites/`.

Status: Forge first slice is `python -m forge apply --dry-run` (ruleset JSON only; no live apply in CI). Overlay slice 1 is `python -m overlay validate` / `select` / receipt. No `generate` or `run` yet.

- **完整详细设计：** [`docs/design.md`](docs/design.md)
- Inbox 输入面：[`docs/inbox.md`](docs/inbox.md)
- 测试体系规格（两棵树 + 接入方自选 `function_id`）：[`docs/test-spec.md`](docs/test-spec.md)
- Agent skill（IEEE 子集）：[`docs/agents/ieee-test-system.md`](docs/agents/ieee-test-system.md)
- Agent：读文档编成契约 [`docs/agents/overlay-contract.md`](docs/agents/overlay-contract.md)；IEEE 剖面 [`docs/agents/ieee-test-system.md`](docs/agents/ieee-test-system.md)
- 产品怎么接到别的仓：[`docs/products.md`](docs/products.md)
- 约束：[`docs/2026-09-10-对话整理.md`](docs/2026-09-10-对话整理.md)
- Overlay 契约：[`schema/suite.schema.json`](schema/suite.schema.json)、[`schema/inbox.schema.json`](schema/inbox.schema.json)、[`schema/trace.schema.json`](schema/trace.schema.json)、[`schema/receipt.example.yaml`](schema/receipt.example.yaml)
- LG fixture（已编译例）：[`examples/learning-guide/`](examples/learning-guide/)
- Forge 政策：[`forge/agent-policy.md`](forge/agent-policy.md)、[`forge/ruleset.protected-default.json`](forge/ruleset.protected-default.json)
