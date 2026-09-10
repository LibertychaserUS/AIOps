# SOP 索引

给人对照。Agent 先读对应 skill，再读本文。

格式：Agent Skills 的 `SKILL.md`（YAML `name` + `description`，`name` 等于目录名）。仓内路径 `skills/<name>/`。发现路径（同一批 symlink）：`.agents/skills/`（Codex）、`.cursor/skills/`（Cursor）、`.claude/skills/`（Claude Code）。

| 产品 / 角色 | 人怎么做 | Agent 怎么做 |
|---|---|---|
| **Forge** | [`skills/use-forge/SKILL.md`](../skills/use-forge/SKILL.md) | 同一文件 + [`../forge/agent-policy.md`](../forge/agent-policy.md) |
| **Overlay** | [`skills/use-overlay/SKILL.md`](../skills/use-overlay/SKILL.md) | 同一文件 + [`agents/overlay-contract.md`](agents/overlay-contract.md) + [`../skills/design-cases/SKILL.md`](../skills/design-cases/SKILL.md) |
| **用例设计** | [`skills/design-cases/SKILL.md`](../skills/design-cases/SKILL.md) | 同一文件（旧入口 [`agents/case-design.md`](agents/case-design.md)） |
| **管理端**（Ruleset / merge / arm） | [`skills/manage-repo/SKILL.md`](../skills/manage-repo/SKILL.md) | 不扮演管理端：不 apply、不合、不写 `reviewed_by`、不替开发 push |
| **开发端**（`forge check` + `FORGE_SUBMIT_TOKEN` + `forge submit` / 修 armed 红） | [`skills/dev-pr/SKILL.md`](../skills/dev-pr/SKILL.md) | 同一文件 + [`../forge/agent-policy.md`](../forge/agent-policy.md)；提交前 `check` 必须绿，且持有非空 `FORGE_SUBMIT_TOKEN`（`FORGE_SUBMIT_TOKEN`）；`submit` 开草稿 PR；不自合 |
| **PR 名 / 解说规格** | [`pr-brief.md`](pr-brief.md) + `python -m forge pr-title` + [`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md) | Conventional Commits `type(product/actor): subject`。检查名 `pr-title`。正文六节。不改分支 / workflow / skill 名 |
| **程序锁** | [`sop-lock.md`](sop-lock.md) | skill 能机器判定的标准必须有检查。**代推锁** `python -m forge check`（不绿不 push）。**通用检查 ≠ 产品门。** 通用合入锁 `pr-title`、`sop-lock`（永远跑）。产品门 `overlay-check` / `forge-check`（`forge.yaml` `ci` 选跑或跳过） |
| **CI 设计** | [`ci-design.md`](ci-design.md) | **通用检查 ≠ 产品门**（谁跑）+ **产品前缀分治**（谁住哪个文件）。同前缀可合，跨产品不合。`release.yml` 不是 CI |

PR 的 review 和 merge：**GitHub 上的人 + Ruleset**，不是 Overlay，不是自建管理端。RBAC：[`rbac.md`](rbac.md)。CodeRabbit 只建议，不能当唯一 merge 门。开发写解说规格，管理拒收 `pr-title` 红或正文缺六节的 PR。标题 `actor` 不是分支名。Ruleset 勾上通用 `pr-title`、`sop-lock` 和产品 `overlay-check`、`forge-check` 之后，红则不能合。产品门按 `forge.yaml` 选跑或跳过成功。

Overlay 的测试规格（`suites/`）和 Overlay CI（`overlay-check`）是一条链：只跑 Overlay `armed` 的 `product_command`。不要再开 `self-test` 绕过 Overlay select。不要把 `forge-apply` 标 armed 当代 Overlay 门。Forge 单测走 **`forge-check`**。

不是门户，不是第二本 PRD。设计对照仍是 [`design.md`](design.md)。接到别的仓：[`products.md`](products.md)。

---

## 接到其他项目：工具不进产品仓

外来 agent 导入 skill：根 README「Native skills」；`gh skill install LibertychaserUS/AIOps --pin <tag>`。本仓发现路径：`.agents/skills`（Codex）、`.cursor/skills`（Cursor）、`.claude/skills`（Claude Code）。发布：[`release.md`](release.md)。

**不要把工具上传到接入方要提交、推送的产品 Git 仓。** 工具留在本工作本的本地 git，或接入方 **fork** 的本工作本。产品仓只留薄配置；CI 用 `uses:` 调用工具仓的 reusable workflow（pin **tag 或 SHA**，不要浮动 `main`）。

| 留在 `LibertychaserUS/AIOps` 或它的 fork | 产品仓可以提交 |
|---|---|
| `forge/`、`overlay/`、`schema/`、`prompts/`、本工作本的 Python 包 | `forge.yaml` / `overlay.yaml` / `inbox/` / `suites/` / 可选 `invariants.yaml` / 一条薄 workflow |

本地 CLI：把工具仓或 fork checkout 在产品仓旁边，设 `PYTHONPATH`。不要为了 import 把 `forge/`、`overlay/` `git add` 进产品树。

CI：产品仓没有 `overlay/` 时，[`.github/workflows/overlay.yml`](../.github/workflows/overlay.yml) 会 checkout `LibertychaserUS/AIOps` 到 `_aiops`。这是正确复用路径，不是「把包拷进产品仓」。

禁止（skill 已写死）：

- 对 `LearningGuidePortal` 做 live `forge apply`；不要从本工作本 checkout 该仓；不改 Verify
- push 时 `generate`；agent 写 `reviewed_by` / 回执 / `armed`；CI 自动 armed；agent 自 merge / 自 Approve
- 自建管理端 / 开发端门户，或第二套权限库（RBAC 见 [`rbac.md`](rbac.md)）
- attach / 跑 / 门禁实习仓 Proctor；改 Deepseek3；打生产（`ilovelearningguide.com`）；做 CD
