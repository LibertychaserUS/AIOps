# 两件产品：怎么做、怎么复用

本仓是工作本，不是某一家业务仓。做出两件 **可接到任意 GitHub 仓** 的产品（产品仓只留薄配置，不 vendor 工具包）。最小接入示例：[`../examples/acme-python/`](../examples/acme-python/)。带口音的 fixture：[`../examples/learning-guide/`](../examples/learning-guide/)。

| 产品 | 一句话 |
|---|---|
| **Forge** | 开发侧代推开 PR（`submit` 到 `protect[0]`）；Ops 侧检查绿了人来合；`promote` 开保护分支之间的 PR。不直推 protect，不合入 |
| **Overlay** | 需求 → 可审用例；push 只跑 `active`；`blocked` 丢掉且不当红；不替代接入方已有构建门 |

两件产品独立版本、独立接入、独立失败。接入方可以只装一件。决定：[ADR 0001](adr/0001-two-products-one-repo.md)。

**通用检查 ≠ 产品门。** 文件归属是 **产品前缀分治**（[`ci-design.md`](ci-design.md)）：同前缀可合，跨产品不合。仓级规格永远跑。产品门按 `forge.yaml` `branches:` 选择。不要把标题检查只挂在 Forge 下。

现状：[`STATE.md`](STATE.md)。CLI：[`cli.md`](cli.md)。升级：[`migration-v2.md`](migration-v2.md)。设计：[`design.md`](design.md)。Skills 索引：[`sop.md`](sop.md)。RBAC：[`rbac.md`](rbac.md)。PR：[`pr-brief.md`](pr-brief.md)。Inbox：[`inbox.md`](inbox.md)。测试规格：[`test-spec.md`](test-spec.md)。

---

## 复用：工具不进产品仓

**不要把工具（`forge/`、`overlay/`、`schema/`、`prompts/`、本工作本的 Python 包）上传到接入方要提交、推送的产品 Git 仓。** 工具留在工作本的本地 git，或接入方 **fork**。

产品仓只提交薄层：

| 产品仓提交 | 不提交 |
|---|---|
| `forge.yaml` / `overlay.yaml` | `forge/` 包、`overlay/` 包 |
| `inbox/` / `suites/` / 可选 `invariants.yaml` | `schema/`、`prompts/` |
| 一条薄 workflow：`uses:` 工具仓 reusable，pin **tag 或 SHA** | 整树 vendor / submodule |

本地：`PYTHONPATH=<工具仓>`。CI：产品仓没有 `overlay/__init__.py` 时，reusable 会 checkout `tool_repository` 到 `_aiops`。Fork 把 `uses:` / `tool_repository` / `tool_ref` 指到该 fork。永不 checkout 外国产品仓。

---

## 共同规矩

- 账本是 **产品仓自己的 GitHub 仓**。
- 交付物是 **模板 + CPython CLI + reusable workflow**，不是 SaaS。
- 标准 CPython 3.12+。
- 不做 CD。不打接入方生产域名。不改接入方已有构建 workflow。
- 不 attach 监考进程。不对 `forbidden_live_repos` live apply。
- Agent 只开 PR，不直推保护分支，不自 merge，不写 Overlay 回执，不在 agent 枝上标 `blocked`。token 只在人点的 `generate`。
- PR review / merge：**GitHub 上的人 + Ruleset**。见 [`rbac.md`](rbac.md)。

---

## 产品 A — Forge

开发侧：先 `check` 绿，且持有 `FORGE_SUBMIT_TOKEN`，再 `submit`。Ops 侧：按分支 Ruleset + 人点 merge。完整分工：[`rbac.md`](rbac.md)、[`design.md`](design.md) §3。

接入：

1. 产品仓只加 `forge.yaml`（`protect`、`branches:`、`deny_paths`；`required_checks` 用真实 CI job 名）。
2. 把 `agent-policy.md` **文本**贴进 `AGENTS.md`。
3. 按需把 CODEOWNERS 文本贴进产品仓。
4. Ops：`python -m forge apply --repo owner/name`（先 `--dry-run`）。
5. 把「构建已绿」设为 required check（用接入方自己的 job 名）。

成功标准：`apply` 后普通人与 agent 不能直推保护分支；能开 PR；政策文件在仓里可审。与是否安装 Overlay 无关。

---

## 产品 B — Overlay

先有可审用例，再按状态跑。状态只有 `active` | `blocked`。迁移：[`migration-v2.md`](migration-v2.md)。

接入：产品仓提交 `inbox/`、`suites/`、`overlay.yaml`、薄 `overlay-check.yml` `uses:` pin。本地 `python3 -m overlay validate --root <产品仓>`。`setup_command` 装产品工具链。

成功标准：丢一篇需求进 inbox，当天有一页人审用例；`blocked` 不让 overlay check 变红；`select` 可在无密钥的 Actions 里跑。

---

## 两件产品怎么接

```text
任意项目 GitHub 仓
    │
    ├─ 只装 Forge     → 开发有序，仍无需求对齐用例
    ├─ 只装 Overlay   → 有用例门，人仍可能直推保护分支
    └─ 两件都装（推荐）
         Forge Ruleset 可把 Overlay check 标成 required
         Overlay 红 = active 集红，不是构建门红
```

禁止：Overlay 去改接入方构建 workflow；Forge 去改 `suite.yaml` 的 `status`；一个二进制包死绑某产品路由或生产域名。

---

## 本仓怎么长

这是工具工作本的树，不是产品仓该拷的树。版本：两个产品两个 tag。起步：[`../README.md`](../README.md) / [`../README.zh-CN.md`](../README.zh-CN.md)。
