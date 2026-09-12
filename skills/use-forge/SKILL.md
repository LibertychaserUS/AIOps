---
name: use-forge
description: >-
  Developer cold start for Forge — pin a published tag, pip install,
  PYTHONPATH, python -m forge check, then submit a draft PR to protect[0]
  (usually dev). Live apply belongs to manage-repo. Do not merge. Do not
  submit when local check is red.
metadata:
  short-description: Forge cold start six steps; submit to dev; no live apply
---

# Use Forge

开发冷启动六步：pin → 装依赖 → 写薄 `forge.yaml` → 贴政策文本 → `check` → `submit` 到 `protect[0]`。不合入。不改 Overlay 套件 `status`。

live `apply`、合入、套件 `blocked` 只在 [`../manage-repo/SKILL.md`](../manage-repo/SKILL.md)。开 PR 细节在 [`../dev-pr/SKILL.md`](../dev-pr/SKILL.md)。密钥细节只看 [`../../docs/submit-credential.md`](../../docs/submit-credential.md)，不要把 `FORGE_SUBMIT_TOKEN` 和 Ops 的 `FORGE_GITHUB_TOKEN` 写进同一步。

Pin **已经存在的** tag。当前已发布：`overlay-v2.0.0` / `forge-v1.1.2`。不要 pin `main`。不要 checkout 不存在的 tag。不要 force-move 旧针。现状只看 [`../../docs/STATE.md`](../../docs/STATE.md)。起步：[`../../README.zh-CN.md`](../../README.zh-CN.md)。

`python -m forge --help` 才是子命令清单。没有 `brief` / `credential` / `ops-chain` / `revoke`。

## Lock / 不绿不能合

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

- **代推锁：** `python -m forge check` 必须绿，且持有非空 `FORGE_SUBMIT_TOKEN`。缺密钥或 check 红：`submit`（含 `--dry-run`）退出 2。
- GitHub required checks 锁**合入**。`required_checks` 必须是 **CI job 名**（PR 页面上的字符串），不要抄别人仓的 workflow 名。
- **通用检查 ≠ 产品门。** `pr-title` / `sop-lock` 是通用检查；`overlay-check` / `forge-check` 是产品门。
- 进保护分支默认 squash：**封顶**再压，压完**换底**。
- Agent 不 live-apply。

## Instructions

### 1. Checkout a published pin beside the product

```text
git clone <tool-repo-url> /tmp/AIOps
cd /tmp/AIOps
git checkout overlay-v2.0.0
# Forge CLI: git checkout forge-v1.1.2
```

需要 CPython **3.12+**。不要把 `forge/` vendor 进产品仓。

### 2. Install Python deps

```text
python3 -m pip install -r requirements.txt
export PYTHONPATH=/tmp/AIOps
```

### 3. Write thin `forge.yaml`

抄 [`forge/forge.example.yaml`](../../forge/forge.example.yaml)。设 `protect: [dev, main]`、`branches:`、`agent_branch_prefixes`、`deny_paths`、`docs_sync`、`title.scopes`。`required_checks` = 接入方 PR 上真实的 **CI job 名**。不要抄别人仓的 workflow 名。

产品仓**已经有**能跑的 `overlay-check.yml` / `forge-check.yml`（inline 或 reusable）就保持原形状，不要再抄一份。

### 4. Paste policy text; do not copy `forge/`

把 [`forge/agent-policy.md`](../../forge/agent-policy.md) 的条文贴进产品仓 `AGENTS.md`。是**文本**，不是 `git add forge/`。

### 5. `python -m forge check` from the product cwd

```text
cd /path/to/product
PYTHONPATH=/tmp/AIOps python3 -m forge check --root .
```

有 `overlay.yaml` 时跑 validate + cover。叶子必须是 `### Functional` / `### Negative` / `### Edge`。不要写 `### Depth` 或 `## Specified`。红 → 停。不要 push。不要 submit。

### 6. Submit a draft PR onto protect[0]

持有 `FORGE_SUBMIT_TOKEN`。然后走 [`../dev-pr/SKILL.md`](../dev-pr/SKILL.md)：

```text
PYTHONPATH=/tmp/AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(forge/agent): subject" --dry-run
PYTHONPATH=/tmp/AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(forge/agent): subject"
```

永不 merge。永不自批。永不 live-apply。

## Never

- 不要 vendor `forge/` / `overlay/`。
- 不要 pin `main`。不要 force-move 已有针。不要 checkout 文档里还没打出来的 tag。
- 不要 live-apply（那是 `$manage-repo`）。
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
| checkout 已发布针失败 | `git fetch --tags` 后再 pin **已存在**的 tag。不要 pin `main`。 |
| `required_checks` 对不上 CI | 改成 PR 上真实的 job 名。 |
| 想 live apply / 直推保护分支 | 停。`$manage-repo` / `$dev-pr`。 |
| 想把套件标 blocked | 停。人写。`$manage-repo`。 |
| 接入方已有自己的落地方式 | 先对照新旧，等人明确同意再写 `forge.yaml`。 |
