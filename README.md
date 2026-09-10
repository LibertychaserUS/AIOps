# AIOps

Workshop for two reusable GitHub products. Not the empty First-Light `AIOps` repo. Learning Guide is the first fixture, not the product.

| Product | Job |
|---|---|
| **Forge** | Make multi-person (and agent) GitHub work ordered: PR-only, reviewed, no direct push to protected branches |
| **Overlay** | Generate reviewable tests; run only `armed` suites. Does not replace a repo’s existing build gate |

Neither deploys. Neither attaches Proctor. Neither edits Learning Guide Verify.

Status: design written; no installer or generator yet.

- **完整详细设计：** [`docs/design.md`](docs/design.md)
- Inbox 输入面：[`docs/inbox.md`](docs/inbox.md)
- 产品怎么接到别的仓：[`docs/products.md`](docs/products.md)
- 约束：[`docs/2026-09-10-对话整理.md`](docs/2026-09-10-对话整理.md)
- Overlay 契约：[`schema/suite.schema.json`](schema/suite.schema.json)、[`schema/inbox.schema.json`](schema/inbox.schema.json)、[`schema/receipt.example.yaml`](schema/receipt.example.yaml)
- LG fixture：[`examples/learning-guide/`](examples/learning-guide/)
- Forge 政策：[`forge/agent-policy.md`](forge/agent-policy.md)、[`forge/ruleset.protected-default.json`](forge/ruleset.protected-default.json)
