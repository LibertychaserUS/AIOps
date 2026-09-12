# 从 overlay-v1.0.x / forge-v1.0.x 升到 v2

权威语言：中文。针只 pin **已经存在的 tag 或 SHA**，不要 pin 浮动 `main`。不要 force-move `1.0.0` / `1.0.1`。

CLI 清单见 [`cli.md`](cli.md)。字段权威：Overlay 契约（合入后 `overlay-contract.md`）、Forge 配置（合入后 `forge-config.md`）。本页只写步骤。

现状页：[`STATE.md`](STATE.md)（生成；没有就先 `forge status --write`）。设计决定：[ADR 0001](adr/0001-two-products-one-repo.md) … [0006](adr/0006-chinese-canonical.md)。

---

## 0. 工具仓 checkout

```text
git clone <本工作本或你的 fork> /tmp/AIOps
cd /tmp/AIOps
git checkout overlay-v2.0.0    # Overlay 已发布针。Forge CLI 另 checkout forge-v1.1.2
python3 -m pip install -r requirements.txt
export PYTHONPATH=/tmp/AIOps
```

需要 CPython 3.12+。不要把 `forge/`、`overlay/` `git add` 进产品仓。

---

## 1. Overlay：契约与套件

在**产品仓**根目录：

```text
python3 -m overlay migrate --root . --dry-run
python3 -m overlay migrate --root .
python3 -m overlay validate --root .
python3 -m overlay cover --root .
```

`migrate` 会：

- `suites/*/suite.yaml`：`draft`/`armed` → `active`；`blocked` 保留。
- 删除 `reviewed_by` / `reviewed_at` / `armed_reason`。
- `blocked` 缺 `blocked_reason`（或 reason 里没有链接 / `OF-*` / `#数字`）→ 不改，打印待办。人补理由后再迁。
- `overlay.yaml` 的 `never_red_statuses` 若含 `draft` 则删掉；v2 只接受 `blocked`。
- 套件文件写上 `schema: overlay-suite/v2`（配置仍是 `overlay-config/v1`）。

逐行改写，不 yaml dump 重排。迁完 diff 应只有状态/字段/schema。

叶子标题仍是 `### Functional` / `### Negative` / `### Edge`。`function_id` 全局唯一。`invariants.yaml` 的 `function_ids` 必须对上某篇 `cases.md` 的 `##` 标题。

`select --branch` 只读 `overlay.yaml` 的 `branches.<name>`；状态读当前 checkout。缺省分支：`GITHUB_BASE_REF` → `GITHUB_REF_NAME` → `main`。未知分支回落 `branches.default` 再到 `main`。

CI：产品仓薄 caller 继续 `uses:` reusable `overlay.yml`，pin **`overlay-v2.0.0`（或 SHA）**。`run` 要 Node / Python / Go / Java 时传 `setup_command`（例如 `pip install -r requirements-dev.txt` 或 `npm ci`）。`--branch` 缺省用 `github.base_ref` / `github.ref_name`。不要 `workflow_call` 接入方构建 workflow。不要 pin `main`。

最小非口音示例：[`examples/acme-python/`](../examples/acme-python/)。Learning Guide 口音的 fixture 仍在 [`examples/learning-guide/`](../examples/learning-guide/)。

---

## 2. Forge：`branches:` 与晋升

把产品仓 `forge.yaml` 从顶层单一规则改成按分支。旧字段仍能读，但 v1.1 推荐显式表。

```yaml
schema: forge-config/v1
protect: [dev, main]          # 第一项 = submit 默认 base
agent_branch_prefixes: [cursor/, copilot/, agent/]
deny_paths: [.github/workflows/]
branches:
  dev:
    required_checks: [unit, lint, overlay-check]
    approvals: 0
    code_owners: false
  main:
    required_checks: [unit, lint, overlay-check, forge-check]
    approvals: 1
    code_owners: true
    promote_from: dev
title:
  scopes: any
docs_sync: []
forbidden_live_repos: []
```

`required_checks` 必须是 PR 上真实的 **CI job 名**。不要抄别的仓、也不要抄 workflow 的 `name:`（除非两个字符串本来一样）。

然后：

```text
python3 -m forge check --root .
python3 -m forge apply --repo OWNER/NAME --dry-run   # 仅 Ops；agent 不 live apply
```

`protect` 只有 `main`、没有 `dev` 的仓：可以暂缓 `promote`，但 `branches.main` 仍建议写清批准数与 CODEOWNERS。

晋升（有 `dev` 且 `promote_from`）：

```text
python3 -m forge promote --repo OWNER/NAME --from dev --to main --dry-run
```

永不 merge。人在 GitHub 上批 + CODEOWNERS 后点合。

---

## 3. CI pin

| 产品仓文件 | 旧针 | 新针 |
|---|---|---|
| `.github/workflows/overlay-check.yml` 的 `uses:` | `overlay-v1.0.0` / `overlay-v1.0.1` | `overlay-v2.0.0` 或该 SHA |
| `tool_ref` | 同上 | 与 `uses:` 同一 pin |
| 若另 pin Forge reusable | `forge-v1.0.1` | `forge-v1.1.0` |

不要 pin `main` / `master` / `HEAD` / `latest`。Fork 把 `uses:` / `tool_repository` / `tool_ref` 指到该 fork 的 pin。

工作本自己的 `unittest` job 永远跑；接入方不必拷工作本 `ci.yml`。

---

## 4. CODEOWNERS 与人审

v2 不再用 `reviewed_by` 当用例签字。补：

```text
docs/** AGENTS.md skills/** .github/** schema/** @<你的维护者>
```

工作本示例：[`.github/CODEOWNERS`](../.github/CODEOWNERS)。`branches.main.code_owners: true` 时 Ruleset 会要求这些路径的审查。

解禁（`blocked` → `active`）走 PR，理由写在 `blocked_reason` 的链接里（issue / ADR / CHANGELOG 段）。

---

## 5. 文档与 skill

- 产品仓 `AGENTS.md`：贴 `forge/agent-policy.md` 文本，不要拷 `forge/` 目录。
- 工具仓 skill：`gh skill install <owner>/<workshop> --agent cursor --pin overlay-v2.0.0`（host id：`codex` / `cursor` / `claude-code` / `github-copilot`）。
- 本工作本文档：现状只看 STATE；子命令只看 `docs/cli.md`。

---

## 6. 验收

产品仓：

```text
PYTHONPATH=/tmp/AIOps python3 -m overlay validate --root .
python3 -m overlay cover --root .
python3 -m forge check --root .
```

工作本（集成者）：全量 unittest、`forge check`、`sop-lock`、生成 `docs/cli.md` 与 `docs/STATE.md`。

任一红：停。不要 submit，不要 pin 浮动 `main`。
