# SOP 索引

给人对照。Agent 先读对应 skill，再读本文。入口：[`../AGENTS.md`](../AGENTS.md)。现状：[`STATE.md`](STATE.md)。CLI：[`cli.md`](cli.md)。

格式：Agent Skills 的 `SKILL.md`（YAML `name` + `description`，`name` 等于目录名）。仓内路径 `skills/<name>/`。发现路径：`.agents/skills/`、`.cursor/skills/`、`.claude/skills/`。

| 产品 / 角色 | 人怎么做 | Agent 怎么做 |
|---|---|---|
| **Forge** | [`skills/use-forge/SKILL.md`](../skills/use-forge/SKILL.md) | 同一文件 + [`../forge/agent-policy.md`](../forge/agent-policy.md) |
| **Overlay** | [`skills/use-overlay/SKILL.md`](../skills/use-overlay/SKILL.md) | 同一文件 + [`agents/overlay-contract.md`](agents/overlay-contract.md) + [`../skills/design-cases/SKILL.md`](../skills/design-cases/SKILL.md) |
| **用例设计** | [`skills/design-cases/SKILL.md`](../skills/design-cases/SKILL.md) | 同一文件（旧入口 [`agents/case-design.md`](agents/case-design.md)） |
| **管理端**（Ruleset / merge / 隔离） | [`skills/manage-repo/SKILL.md`](../skills/manage-repo/SKILL.md) | 不扮演管理端：不 apply、不合、不替开发 push |
| **开发端**（`forge check` + `FORGE_SUBMIT_TOKEN` + `submit` / 修 active 红） | [`skills/dev-pr/SKILL.md`](../skills/dev-pr/SKILL.md) | 同一文件 + agent-policy；提交前 `check` 必须绿；`submit` 开草稿 PR；不自合 |
| **PR 名 / 解说规格** | [`pr-brief.md`](pr-brief.md) + 模板 | Conventional Commits。正文六节。不改分支 / workflow / skill 名 |
| **程序锁** | [`sop-lock.md`](sop-lock.md) | skill 能机器判定的标准必须有检查。**代推锁** `python -m forge check`。**通用检查 ≠ 产品门。** 通用合入锁 `pr-title`、`sop-lock`；工作本 `unittest` 永远跑。产品门按分支 |
| **CI 设计** | [`ci-design.md`](ci-design.md) | **通用检查 ≠ 产品门** + **产品前缀分治**。`release.yml` 不是 CI |

PR 的 review 和 merge：**GitHub 上的人 + Ruleset**。RBAC：[`rbac.md`](rbac.md)。CodeRabbit 只建议。开发写解说规格，管理拒收标题红或正文缺六节的 PR。进保护分支 **squash 封顶**；合完 **换底**。

Overlay 的测试规格（`suites/`）和 Overlay CI 是一条链：只跑 `active` 的 `product_command`。不要再开旁路绕过 Overlay select。不要把 Forge 单测标进 Overlay run。Forge 单测走 **`forge-check`** 或工作本 `unittest`。

不是门户。设计对照：[`design.md`](design.md)。接到别的仓：[`products.md`](products.md)。

---

## 接到其他项目：工具不进产品仓

外来 agent 导入 skill：根 README；`gh skill install <owner>/<workshop> --pin <tag>`。发布：[`release.md`](release.md)。

**不要把工具上传到接入方要提交、推送的产品 Git 仓。** 工具留在本工作本或 fork。产品仓只留薄配置；CI 用 `uses:` pin **tag 或 SHA**。

| 留在工作本或 fork | 产品仓可以提交 |
|---|---|
| `forge/`、`overlay/`、`schema/`、`prompts/`、Python 包 | `forge.yaml` / `overlay.yaml` / `inbox/` / `suites/` / 可选 `invariants.yaml` / 一条薄 workflow |

本地 CLI：`PYTHONPATH` 指向工具仓。CI：产品仓没有 `overlay/` 时，reusable 会 checkout 工具仓到 `_aiops`。

禁止：

- 对 `forbidden_live_repos` 做 live `apply`
- push 时 `generate`；agent 写回执；CI 自动解禁；agent 自 merge / 自 Approve
- 自建管理端门户或第二套权限库（[`rbac.md`](rbac.md)）
- attach 监考进程；打生产；做 CD
