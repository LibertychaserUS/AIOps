---
name: use-forge
description: >-
  Developer cold start for Forge v1.1 — pin a published tag, pip install,
  write forge.yaml with per-branch rules, run python -m forge check, then
  submit a draft PR to protect[0] (usually dev). Promote to main is a separate
  command. Live apply belongs to manage-repo. Do not merge. Do not submit
  when local check is red.
metadata:
  short-description: Forge v1.1 cold start; submit to dev; no live apply
---

# Use Forge

Forge 是开发门：本地 `check`，再 `submit`（draft PR 到 `protect[0]`，通常是 `dev`）。不 merge。不改 Overlay 套件 `status`。

**谁审、谁合：** GitHub 人 + Ruleset。开发端：[`../dev-pr/SKILL.md`](../dev-pr/SKILL.md)。管理端（live `apply`、合入、promote 批、套件 `blocked`）：[`../manage-repo/SKILL.md`](../manage-repo/SKILL.md)。

Pin **已发布** tag。当前工作本目标是 `overlay-v2.0.0` / `forge-v1.1.0`（见 [`../../CHANGELOG.md`](../../CHANGELOG.md)）。已存在的 `overlay-v1.0.1` / `forge-v1.0.1` 仍可 pin。不要 pin `main`。不要 force-move 旧针。起步：[`../../README.md`](../../README.md)。

## Real CLI

`python -m forge --help`：

`apply` `status` `check` `submit` `promote` `pr-title`/`title` `sop-lock` `ci-select` `ops-review` `bounce` `release`

没有 `brief` / `credential` / `ops-chain` / `revoke`。密钥：[`docs/submit-credential.md`](../../docs/submit-credential.md)。

| 动作 | Agent | 人 / Ops |
|---|---|---|
| `forge check` | 可以 | — |
| `forge submit` 到 `dev` | 可以（`FORGE_SUBMIT_TOKEN`） | — |
| `forge promote` | 可以（同一把 token；只开 PR） | 可以 |
| live `forge apply` | **不可以** | Ops（`$manage-repo`） |
| merge | **不可以** | 人 |

`FORGE_SUBMIT_TOKEN` 是代推钥匙。Ops `FORGE_GITHUB_TOKEN` 是 Ruleset 钥匙。不要混。`gh auth` / `GITHUB_TOKEN` 不够。

## Lock / 不绿不能合

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

- **代推锁：** `python -m forge check` 必须绿 **并且** 持有非空 `FORGE_SUBMIT_TOKEN`。缺密钥或 check 红：`submit` / `promote`（含 `--dry-run`）退出 2。
- GitHub required checks 锁**合入**。`required_checks` 必须是 **CI job 名**（PR 页面上的字符串）。
- **通用检查 ≠ 产品门。** `pr-title` / `sop-lock` 是通用检查；`overlay-check` / `forge-check` 是产品门；工作本另有永远跑的 `unittest`。
- 进保护分支默认 squash：**封顶**再压，压完**换底**。`submit` base 是 `protect`（默认 `protect[0]`）。
- 不绿不能提交。不绿不能合。Agent 不 live-apply。

配置权威：[`docs/forge-config.md`](../../docs/forge-config.md)。路径图：[`docs/dev-main-flow.md`](../../docs/dev-main-flow.md)。

## Instructions

### 1. Checkout a published pin beside the product

```text
git clone <tool-repo-url> /tmp/AIOps
cd /tmp/AIOps
git checkout overlay-v1.0.1
```

需要 CPython **3.12+**。不要把 `forge/` vendor 进产品仓。

### 2. Install Python deps

```text
python3 -m pip install -r requirements.txt
export PYTHONPATH=/tmp/AIOps
```

### 3. Write thin `forge.yaml`

抄 [`forge/forge.example.yaml`](../../forge/forge.example.yaml)。设 `protect: [dev, main]`、`branches:`、`agent_branch_prefixes`、`deny_paths`、`docs_sync`、`title.scopes`。`required_checks` = 接入方真实的 CI job 名。不要抄别人的 workflow 名。

### 4. Paste policy text; do not copy `forge/`

把 [`forge/agent-policy.md`](../../forge/agent-policy.md) 的条文贴进产品仓 `AGENTS.md`。是**文本**，不是 `git add forge/`。

### 5. `python -m forge check` from the product cwd

```text
cd /path/to/product
PYTHONPATH=/tmp/AIOps python3 -m forge check --root .
```

有 `overlay.yaml` 时跑 validate + cover。接入方根目录（没有 `overlay/__init__.py`）不打印工作本专用步骤。红 → 停。不要 push。不要 submit。

### 6. Submit a draft PR onto protect[0]

持有 `FORGE_SUBMIT_TOKEN`。然后 [`../dev-pr/SKILL.md`](../dev-pr/SKILL.md)：

```text
PYTHONPATH=/tmp/AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(forge/agent): subject" --dry-run
PYTHONPATH=/tmp/AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(forge/agent): subject"
```

永不 merge。永不自批。永不 live-apply。诊断 Ruleset 只用 `--dry-run` apply。

`docs_sync` 与 `docs/STATE.md`：改 `forge/**` 时同步改 CHANGELOG / 配置文档；需要状态页时 `python -m forge status --repo O/N --root . --write docs/STATE.md`。

## Never

- 不要 vendor `forge/` / `overlay/`。
- 不要 pin `main`。不要 force-move 已有针。
- 不要 live-apply。
- 不要发明 `python -m forge brief|credential|ops-chain|revoke`。
- 不要在 agent 分支把套件标成 `blocked`。

## Examples

```text
PYTHONPATH=/tmp/AIOps python3 -m forge check --root . --title "feat(overlay/agent): add cover triad"
PYTHONPATH=/tmp/AIOps python3 -m forge submit --repo OWNER/PRODUCT --title "feat(overlay/agent): add cover triad" --dry-run
```

非法：`required_checks` 写成别人仓的 workflow 名。非法：live `forge apply`。非法：pin `main`。

## Performance Notes

`check` 是本地的。密钥细节只在 [`docs/submit-credential.md`](../../docs/submit-credential.md)。

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想把 `forge/` 拷进产品仓 | 停。工具留在 sibling checkout。 |
| checkout 已发布针失败 | `git fetch --tags` 后再 pin。不要 pin `main`。 |
| `required_checks` 对不上 CI | 改成 PR 上真实的 job 名。 |
| 想 live apply / 直推保护分支 | 停。`$manage-repo` / `$dev-pr`。 |
| 想把套件标 blocked | 停。人写。`$manage-repo`。 |
| 接入方已有自己的落地方式 | 先对照新旧，等人明确同意再写 `forge.yaml`。 |
