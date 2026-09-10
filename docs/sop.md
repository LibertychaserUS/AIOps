# SOP 索引

给人对照。Agent 先读对应 skill，再读本文。

格式：Codex / Agent Skills 的 `SKILL.md`（YAML `name` + `description`，`name` 等于目录名）。仓内路径 `skills/<name>/`；Codex 还会读 `.agents/skills/`（同一批 skill 的符号链接）。

| 产品 | 人怎么做 | Agent 怎么做 |
|---|---|---|
| **Forge** | [`skills/use-forge/SKILL.md`](../skills/use-forge/SKILL.md) | 同一文件 + [`../forge/agent-policy.md`](../forge/agent-policy.md) |
| **Overlay** | [`skills/use-overlay/SKILL.md`](../skills/use-overlay/SKILL.md) | 同一文件 + [`agents/overlay-contract.md`](agents/overlay-contract.md) + [`../skills/design-cases/SKILL.md`](../skills/design-cases/SKILL.md) |
| **用例设计** | [`skills/design-cases/SKILL.md`](../skills/design-cases/SKILL.md) | 同一文件（旧入口 [`agents/case-design.md`](agents/case-design.md)） |

Overlay 的测试规格（`suites/`）和 CI（`overlay-check`）是一条链：只跑 `armed` 的 `product_command`。不要再开一套旁路 unittest workflow。

不是门户，不是第二本 PRD。设计对照仍是 [`design.md`](design.md)。接到别的仓：[`products.md`](products.md)。

---

## 接到其他项目：工具不进产品仓

**不要把工具上传到接入方要提交、推送的产品 Git 仓。** 工具留在本工作本的本地 git，或接入方 **fork** 的本工作本。产品仓只留薄配置；CI 用 `uses:` 调用工具仓的 reusable workflow（pin **tag 或 SHA**，不要浮动 `main`）。

| 留在 `LibertychaserUS/AIOps` 或它的 fork | 产品仓可以提交 |
|---|---|
| `forge/`、`overlay/`、`schema/`、`prompts/`、本工作本的 Python 包 | `forge.yaml` / `overlay.yaml` / `inbox/` / `suites/` / 可选 `invariants.yaml` / 一条薄 workflow |

本地 CLI：把工具仓或 fork checkout 在产品仓旁边，设 `PYTHONPATH`。不要为了 import 把 `forge/`、`overlay/` `git add` 进产品树。

CI：产品仓没有 `overlay/` 时，[`.github/workflows/overlay.yml`](../.github/workflows/overlay.yml) 会 checkout `LibertychaserUS/AIOps` 到 `_aiops`。这是正确复用路径，不是「把包拷进产品仓」。

禁止（skill 已写死）：

- 对 `LearningGuidePortal` 做 live `forge apply`；不要从本工作本 checkout 该仓；不改 Verify
- push 时 `generate`；agent 写 `reviewed_by` / 回执 / `armed`；CI 自动 armed
- attach / 跑 / 门禁实习仓 Proctor；改 Deepseek3；打生产（`ilovelearningguide.com`）；做 CD
