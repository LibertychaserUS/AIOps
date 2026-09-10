# Review / merge 与 RBAC

PR 的 **review 和 merge 由 GitHub 上的人 + Repository Ruleset 管**，不是 Overlay，不是 Forge CI，也不是本仓自建的管理端。

控制面只有这一套：

- GitHub org **teams**（谁是 admin / maintainer / writer）
- Repository **Ruleset**（禁直推、必须 PR、批准数、required checks）。本工作本声明的 check 名：`overlay-check`、`pr-title`（见 `forge.yaml`）。`pr-title` 红则不合。。本工作本声明的 check 名：`overlay-check`、`pr-title`（见 `forge.yaml`）。`pr-title` 红则不合。
- **CODEOWNERS**（哪条路径必须谁审）
- Overlay `suite.yaml` 的人审字段（`reviewed_by`、`armed` / `blocked`）

不要第二套权限库、不要 admin Web、不要数据库 RBAC、不要为角色再做一个门户。协作仍在 **GitHub + CodeRabbit**。Forge 不重做 diff 审。CodeRabbit **只建议，不能当唯一 merge 门**。

角色怎么干活：管理端 [`../skills/manage-repo/SKILL.md`](../skills/manage-repo/SKILL.md)，开发端 [`../skills/dev-pr/SKILL.md`](../skills/dev-pr/SKILL.md)。产品 SOP 仍是 [`../skills/use-forge/SKILL.md`](../skills/use-forge/SKILL.md) 与 [`../skills/use-overlay/SKILL.md`](../skills/use-overlay/SKILL.md)。PR 解说面：[`pr-brief.md`](pr-brief.md)。

---

## 谁合 PR

人合。Ruleset 要求的 required checks 绿、批准数够，**有 write 的人**（通常是 maintainer / admin）在 GitHub 上点 merge。

| 谁 | 能不能合 |
|---|---|
| 管理端（repo admin / maintainer） | 能，且负责装门、勾 check、写 CODEOWNERS |
| 开发端（有 write 的人） | 能合**别人**的、已绿且已批准的 PR；不要合自己让 agent 开的 PR |
| Agent（Copilot / Cursor） | **不能**自 Approve、**不能**自 merge |
| Overlay / Forge CI | **不管**谁能 merge；只跑 armed 或装政策 |
| CodeRabbit | **不能**当唯一门 |

Agent 只开草稿 PR。模型不写 `reviewed_by`。CI 不自动 `armed`。

---

## 管理端 vs 开发端

| 角色 | GitHub | Overlay | Forge |
|---|---|---|---|
| **管理端**（repo admin / maintainer） | 装 Ruleset、勾 required checks、写 CODEOWNERS / teams、绿+已批准后 merge | 写 `reviewed_by`，标 `armed` / `blocked` | 用 **admin token** `forge apply`；**永不**在 Overlay CI 里 apply |
| **开发端**（人） | 开 PR、修 armed 红、请求 review；不推保护分支 | 写 inbox / suites **草稿**；除非自己也是审的人，否则不 arm | 守 [`../forge/agent-policy.md`](../forge/agent-policy.md)；不写 Ruleset |
| **Agent**（Copilot / Cursor） | 只开草稿 PR；不自 Approve、不自 merge | 人点才可 `generate`（未交付）；永不 arm、永不写回执 | 除人要求的 `--dry-run` 外不 apply |
| **CodeRabbit** | 只建议 | — | — |

RBAC 不另做：GitHub 团队成员资格决定谁能推/合；Ruleset 执行门；CODEOWNERS 点名必须审的人；`suite.yaml` 记录谁审过用例。

---

## Overlay 人审（管理端）

`python -m overlay review --suite ID --status armed|blocked --i-am HUMAN --reason TEXT` 这一刀仍 **拒绝写盘**。管理端 **手改** `suites/<id>/suite.yaml`：

- `status: armed` 或 `blocked`
- 非空 `reviewed_by` + ISO-8601 `reviewed_at`
- `armed` 要 `armed_reason`；`blocked` 要 `blocked_reason`

CI、模型、Forge、Proctor 不得把状态写成 `armed`。

---

## PR 解说面

GitHub PR 的标题 + 正文就是解说面。不是门户。规格：[`pr-brief.md`](pr-brief.md)。模板：[`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)。

- 标题：Conventional Commits `type(product/actor): subject`，必须过 `python -m forge pr-title`。CI 检查名 **`pr-title`**。`actor` 是唯一的名分工标记（`dev`\|`admin`\|`agent`）。不是权限，不改分支名 / workflow 名 / skill 名。`cursor/…-6842` 保持原样。
- 正文六节必须原样：`做了什么` `为什么` `动了哪些门` `怎么验` `不做什么` `分工`
- 正文「分工」写谁审、谁可合（本节）。标题 `actor` 不代替这一节。
- **开发写。管理拒收** `pr-title` 红或正文无规格的 PR。Ruleset 勾上 `pr-title` 之后，红则不能合。

---

## 不做

- 不自建管理端 / 开发端 Web
- 不做 OAuth、GitHub App、自建 RBAC API
- 不把 `forge/`、`overlay/`、`schema/`、`prompts/` vendor 进产品仓（见 [`products.md`](products.md)）
- 不改 LearningGuidePortal Verify；不 attach Proctor；不打生产
