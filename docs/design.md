# Forge + Overlay 设计

实现对照。摘要：[`products.md`](products.md)。Inbox：[`inbox.md`](inbox.md)。测试规格：[`test-spec.md`](test-spec.md)。PR 解说：[`pr-brief.md`](pr-brief.md)。CI：[`ci-design.md`](ci-design.md)。ADR：[`adr/`](adr/)。升级：[`migration-v2.md`](migration-v2.md)。

**现状**（pin、保护分支、Ruleset、CI job 名）只看 [`STATE.md`](STATE.md)，不要在本文写死。**子命令**只看 [`cli.md`](cli.md)。

Overlay 冻字段与对齐方式，不冻某产品的编号或 PRD 树。两棵树用接入方自选的 `function_id` 对齐。

---

## 0. 一句话

做出 **两件可安装到任意 GitHub 仓的产品**，不做成某一家业务的插件，不做成门户，不做成云 agent 舰队。

| 产品 | 解决什么 |
|---|---|
| **Forge** | 人 + agent 写同一仓：只开 PR、有人审、不直推保护分支。`submit` 到 `protect[0]`；`promote` 开保护分支之间的 PR；不合入。 |
| **Overlay** | 需求变成可审用例；CI 跑 `active`；`blocked` 丢掉且不当红 |

第一个接入示例是 [`../examples/acme-python/`](../examples/acme-python/)。带产品口音的 fixture 在 [`../examples/learning-guide/`](../examples/learning-guide/)，不是内核。接入方已有构建门不改、不替代。只做 CI，不做 CD。决定：[ADR 0001](adr/0001-two-products-one-repo.md)。

---

## 1. 问题、用户、非目标

### 1.1 问题

1. 多人（再加会开 PR 的 agent）直推保护分支、互踩、无人审就合。
2. 产品写的需求和开发推的代码对不齐。没就绪的集推进门就会必红。

### 1.2 用户

| 角色 | Forge | Overlay |
|---|---|---|
| 产品 | 开 PR 交 inbox | 往 `inbox/` 丢需求摘录；审 `cases.md` |
| 开发 | `check` 绿且持有 `FORGE_SUBMIT_TOKEN` 后 `submit` | 只修 `active` 红的部分 |
| 测试 | 审 PR | 未就绪标 `blocked`（带链接） |
| Agent | 只开草稿 PR；可 `promote --dry-run` 若人要求 | 可被派去 `generate`（人点）；不能改成 `blocked` |
| 接入方管理员 | `apply`、勾 Ruleset、点 merge、`release` | 写 `overlay.yaml`，挂 reusable workflow |

PR 的 review 和 merge 由 **GitHub Ruleset + 有写权限的人** 管理。RBAC：[`rbac.md`](rbac.md)。

### 1.3 非目标（冻结）

- SaaS、数据库、Web 工作台、自建 RBAC / 管理端门户。
- Graphite 克隆、自动合入。Forge 不合入。
- CD、部署、打接入方生产域名。
- 改接入方已有构建 workflow。
- Forge 改 Overlay 的 `status`；Overlay 改接入方构建 YAML。
- 模型写回执；CI 自动把 `blocked` 改成 `active`。
- 把两件产品焊成一只万能云 agent。

### 1.4 平衡

| 维 | 做法 |
|---|---|
| 可用 | 当天能审一页用例；`apply` 当天能挡住直推 |
| 少闲活 | 开发不注册、不填工单；隔离未就绪改一行 yaml + 链接 |
| token | Overlay 模型密钥只在 `generate`；push 零模型。Forge 代推必须持有 `FORGE_SUBMIT_TOKEN` |
| 速度 | 无服务、无 TS 工具链、无第一刀 C 扩展 |

---

## 2. 总架构

```text
                    任意 GitHub 仓（产品仓）
                    ┌─────────────────────┐
     人 / agent ──► │  Forge（政策+Ruleset）│  只开 PR
                    └──────────┬──────────┘
                               │ 可选：Ruleset required check = Overlay
                               ▼
                    ┌─────────────────────┐
     inbox / PRD ─► │ Overlay（用例+选择） │  只跑 active
                    └──────────┬──────────┘
                               │ checkout pin + product_command
                               ▼
                         产品仓代码与已有测试
                         （不改其构建 workflow）
```

账本：产品仓 Git（薄配置 + `inbox/` / `suites/`）。本工作本只发布模板、CLI、reusable workflow、JSON Schema。  
产品仓不要 vendor `forge/`、`overlay/`、`schema/`、`prompts/`。CLI 用旁边的工作本（`PYTHONPATH`），CI 用 `uses:` 再 checkout 工具仓。  
运行时：GitHub Actions + 标准 CPython 3.12+。  
两件产品独立版本，可只装一件。

---

## 3. Forge

范围、按分支规则、`promote`、`docs_sync`、`title.scopes`、`forbidden_live_repos`：合入后见 `forge-config.md` 与 [ADR 0003](adr/0003-dev-main-promotion.md)、[0004](adr/0004-per-branch-rulesets.md)、[0005](adr/0005-docs-sync-and-state.md)。命令见 [`cli.md`](cli.md)。

对象：

| 对象 | 存哪 |
|---|---|
| 保护分支与规则 | 产品仓 `forge.yaml` → `protect` + `branches:` |
| Agent 分支前缀 | `agent_branch_prefixes`（默认含 `cursor/`、`copilot/`、`agent/`） |
| 禁止改的路径 | `deny_paths` |
| CODEOWNERS | 产品仓 `.github/CODEOWNERS` |
| Agent 政策 | 产品仓 `AGENTS.md`（贴 `forge/agent-policy.md` 文本） |
| 状态页 | `docs/STATE.md`（生成） |

`check`（不写 GitHub）：overlay validate / cover；有 title 时 pr-title；有 `docs/pr-brief.md` 且有 body 时 pr-body；deny_paths；`suite_guard`（agent 分支把套件改成 `blocked` → 红）；`docs_sync`；工作本另加 sop-lock / schema / unittest。接入方根目录（没有 `overlay/__init__.py`）不打印 workshop-only skip。

`submit`：先 `check`；必须 `FORGE_SUBMIT_TOKEN`（缺则含 `--dry-run` 也红）；推功能枝并开/更新 draft PR；base = `protect[0]`；`--base` 必须在 `protect`。永不 merge，永不 approve，永不 apply。`gh auth login` / `GH_TOKEN` / extraheader / `GITHUB_TOKEN` 都不够。见 [`submit-credential.md`](submit-credential.md)。

`apply`：每个保护分支一条 `forge-protected-<branch>`；另有 `forge-protected-tags`。认证 `FORGE_GITHUB_TOKEN`。`--dry-run` 打印全部 payload。

`promote`：需要 `FORGE_SUBMIT_TOKEN`。已有 open PR 则更新，否则创建（非 draft）。永不 merge。

进保护分支默认 **squash 封顶**；合完 **换底**。不要从即将被压掉的旧头再叠。

错误码：0 成功；2 缺 token / check 红；3 配置非法 / 标题不过 / 禁仓；4 GitHub API 失败。

---

## 4. Overlay

状态机（两种，不许更多）：[ADR 0002](adr/0002-remove-armed.md)。

```text
inbox / 人手写 ──► active
                      │
                      │ 人审（未就绪）
                      ▼
                   blocked   （blocked_reason 含链接；select 丢掉、不当红）
```

| status | 含义 | select | 使 Overlay check 红？ |
|---|---|---|---|
| `active`（缺省） | 声称可测 | 纳入该分支 kind | 跑失败才红 |
| `blocked` | 已隔离，功能未就绪 | 丢弃并打印 reason | 否 |

禁止：CI、模型、Forge 把 `blocked` 改成 `active`，或在 agent 分支上新标 `blocked`（`suite_guard`）。

产品仓提交薄层：`inbox/`、`suites/`、`overlay.yaml`、可选 `invariants.yaml`、一条 `uses:` reusable 的 workflow。不要提交 `overlay/` 包。

`suites/<id>/suite.yaml`：`schema: overlay-suite/v2`；`status` 仅 `active`|`blocked`；v1 审核字段出现即红，提示 `overlay migrate`。`blocked` 必须非空 `blocked_reason` 且含 `http(s)://` 或 `OF-12` / `#123`。`product_command` 缺省则 `skipped_no_command`，不红。

`cases.md` 骨架：

```markdown
## FN-login-retry 一句话

### Functional
### Negative
### Edge
```

`function_id`：非空、仓内唯一、稳定、无空白。schema 不把 `REQ-n` 或号段正则写成法律。

`overlay.yaml`（`overlay-config/v1`）：

```yaml
schema: overlay-config/v1
product:
  repo: owner/name
  default_ref: <pin>
branches:
  main: { run: [functional, regression] }
  default: { run: [functional] }
kinds:
  concurrency: later
  agent: later
never_red_statuses: [blocked]
forbid_hosts:
  - prod.example.com
```

`forbid_hosts`：只是命令文本的字符串匹配，防手滑，不是安全边界。

`select`：`--branch X` 只查 `branches.X`；状态读当前 checkout。缺省：`GITHUB_BASE_REF` → `GITHUB_REF_NAME` → `main`。未知分支回落 `branches.default` 再到 `main`，并打印一行说明。

`run`：`bash -c`；`--timeout`；回执记 `exit`、`duration_s`、命令 sha256。命令命中 `forbid_hosts` → 退出 2，不启动。仅 `active` 命令非 0 使 job 红。

`migrate`：见 [`migration-v2.md`](migration-v2.md)。

reusable：pin tag/SHA。`setup_command` 在 caller checkout 装产品工具链。`--branch` 缺省 `github.base_ref` / `github.ref_name`。运行时示例（Node / Python / Go / Java）见合入后的 `overlay-ci.md`。

回执：`wrote_by` 仅 `select` | `run`。模型不得写。无回执的 `run` 退出 2。

`generate`（未交付）是唯一出站 LLM 的命令。禁止 `on: push` 跑 generate。输出必须 `status: active` 的草稿由人经 PR 合入；未就绪人手改 `blocked`。

---

## 5. 组合

只装 Forge：开发有序，无需求对齐用例。只装 Overlay：有用例门，人仍可能直推保护分支。都装：Ruleset 可并列勾构建门 + `overlay-check` +（若装）`forge-check`。

禁止：Forge apply 改 `suite.yaml`；Overlay workflow 改 Ruleset 或构建 YAML；一个 tag 把两件产品绑死。

---

## 6. 技术栈

CPython 3.12+；pip + `requirements.txt`；YAML + JSON Schema；GitHub Rulesets API；Actions `setup-python`；LLM 仅 generate。不用数据库、不用第一刀 C、不改接入方构建 YAML。

---

## 7. 本工作本布局

```text
forge/ overlay/ schema/ prompts/ skills/
examples/acme-python/          # 最小接入
examples/learning-guide/     # 带口音的 fixture
.github/workflows/           # 产品前缀分治
docs/design.md              # 本文
docs/STATE.md               # 生成
docs/cli.md                 # 生成
docs/adr/
CHANGELOG.md
```

发布：`overlay-v*` 与 `forge-v*` 分 tag。CHANGELOG 必须有对应 `## [overlay-X.Y.Z]` / `## [forge-X.Y.Z]` 段。

---

## 8. 安全

- 不提交 `.env`、token、真实支付数据。永不打印 token。
- 代推只读 `FORGE_SUBMIT_TOKEN`。Ops apply 是另一把 `FORGE_GITHUB_TOKEN`。
- Overlay generate 的密钥与 GitHub 凭据不是一把。
- `run` 禁止生产 host（字符串匹配）。
- Guard / select 无出站。`deny_paths` 挡住改构建门。

---

## 9. 切片

第一刀已能装到任意仓：Overlay validate/select/run/receipt；Forge apply/check/submit。v2 加上 migrate、按分支 Ruleset、promote、STATE、docs_sync、acme 示例。`generate` 仍是后一刀。
