# Review / merge 与 RBAC

PR 的 **review 和 merge 由 GitHub 上的人 + Repository Ruleset 管**，不是 Overlay，不是 Forge CI，也不是自建管理端。

控制面只有这一套：

- GitHub org **teams**
- Repository **Ruleset**（禁直推、必须 PR、按分支的批准数与 required checks）。通用检查永远跑；产品门按 `branches:`。代推锁是本地 `python -m forge check`。
- **CODEOWNERS**（哪条路径必须谁审）。这是 v2 里「人签过字」的落点，取代套件上的审核字段。见 [ADR 0002](adr/0002-remove-armed.md)。
- Overlay `blocked` + 带链接的 `blocked_reason`（隔离未就绪，不是签字）

不要第二套权限库、不要 admin Web、不要数据库 RBAC。协作仍在 **GitHub + CodeRabbit**。CodeRabbit **只建议，不能当唯一 merge 门**。进保护分支默认 squash：**封顶**；合完 **换底**。Forge 不合入。

角色：管理端 [`../skills/manage-repo/SKILL.md`](../skills/manage-repo/SKILL.md)，开发端 [`../skills/dev-pr/SKILL.md`](../skills/dev-pr/SKILL.md)。SOP：[`sop.md`](sop.md)。PR 解说：[`pr-brief.md`](pr-brief.md)。现状：[`STATE.md`](STATE.md)。

---

## 开发侧 vs Ops 侧

| 侧 | 谁 | 做什么 | 不做什么 |
|---|---|---|---|
| **开发侧** | 人 / agent + `check` + `submit` | 提交前本地绿，且持有 `FORGE_SUBMIT_TOKEN`，再代推功能枝，开/更新 **draft** PR | 不直推 protect；check 红不 push；缺密钥不 push（含 `--dry-run`）；不自合；不 `apply` |
| **Ops 侧** | 管理端 + Ruleset | 检查绿了人来合。`promote` 开保护分支之间的 PR，仍是人点 merge | 不替开发 push；Forge **不合入**；不当 CodeRabbit 唯一门 |

对齐：`submit` ≈ `gh pr create`（只借代推，不借 stack）。合入门 = Ruleset required checks。人点 merge。

---

## 谁合 PR

人合。Ruleset 要求的 checks 绿、批准数够，**有 write 的人**点 merge。

| 谁 | 能不能合 |
|---|---|
| 管理端 | 能，且负责装门、勾 check、写 CODEOWNERS |
| 开发端 | 能合**别人**的、已绿且已批准的 PR；不要合自己让 agent 开的 PR |
| Agent | **不能**自 Approve、**不能**自 merge |
| Overlay / Forge CI | **不管**谁能 merge |
| CodeRabbit | **不能**当唯一门 |

Agent 只开草稿 PR。CI 不自动解禁 `blocked`。

---

## 管理端 vs 开发端

| 角色 | GitHub | Overlay | Forge |
|---|---|---|---|
| **管理端** | 装 Ruleset、勾 checks、写 CODEOWNERS、绿+已批准后 merge | 手改 `blocked` / `active`（经 PR） | admin token `apply`；**不替开发** `submit` |
| **开发端** | `submit` 开 PR、修 `active` 红 | 写 inbox / suites；不要在 agent 枝上标 `blocked` | 守 [`../forge/agent-policy.md`](../forge/agent-policy.md) |
| **Agent** | `submit` 开草稿 PR | 人点才可 `generate`；永不写回执 | 除人要求的 `--dry-run` 外不 apply |
| **CODEOWNERS** | 路径必审 | — | `branches.<name>.code_owners` |

---

## Overlay 隔离（不是签字）

未就绪：`status: blocked`，`blocked_reason` 含链接或登记编号。解禁走 PR（批准 + CODEOWNERS）。CLI `overlay review` 若仍拒写盘，管理端手改 yaml 也必须经 PR。

CI、模型、Forge 不得把状态写成 `blocked`（agent 枝）或偷偷改成 `active`。

---

## PR 解说面

GitHub PR 的标题 + 正文就是解说面。规格：[`pr-brief.md`](pr-brief.md)。模板：[`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)。

- 标题：Conventional Commits。工作本列出允许 scope；接入方 `title.scopes: any` 时只查语法。检查名 **`pr-title`**。
- 正文六节必须原样：`做了什么` `为什么` `动了哪些门` `怎么验` `不做什么` `分工`
- 模板底部三勾选：文档 / ADR / CHANGELOG。
- **开发写。管理拒收** 标题红或正文无规格的 PR。

---

## 不做

- 不自建管理端 / 开发端 Web
- 不做 OAuth、GitHub App、自建 RBAC API
- 不把工具包 vendor 进产品仓（见 [`products.md`](products.md)）
- 不改接入方构建门；不 attach 监考进程；不打生产
