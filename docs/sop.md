# SOP 索引

给人对照。Agent 先读对应 skill，再读本文。

| 产品 | 人怎么做 | Agent 怎么做 |
|---|---|---|
| **Forge** | [`skills/use-forge/SKILL.md`](../skills/use-forge/SKILL.md) | 同一文件 + [`../forge/agent-policy.md`](../forge/agent-policy.md) |
| **Overlay** | [`skills/use-overlay/SKILL.md`](../skills/use-overlay/SKILL.md) | 同一文件 + [`agents/overlay-contract.md`](agents/overlay-contract.md) |

Overlay 的测试规格（`suites/`）和 CI（`overlay-check`）是一条链：只跑 `armed` 的 `product_command`。不要再开一套旁路 unittest workflow。

不是门户，不是第二本 PRD。设计对照仍是 [`design.md`](design.md)。
