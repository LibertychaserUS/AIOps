---
name: dev-pr
description: >-
  Land a draft PR after python -m forge check is green. Submit onto protect[0]
  (usually dev). Do not apply Rulesets, merge, or set suite status blocked
  (use manage-repo). Do not vendor forge/ or overlay/. Agents must not
  self-merge.
metadata:
  short-description: Open PRs onto dev; do not merge or apply Forge
---

# Dev PR（开发端）

写产品代码和 Overlay 草稿。不管合入锁。SOP：[`../use-forge/SKILL.md`](../use-forge/SKILL.md)、[`../use-overlay/SKILL.md`](../use-overlay/SKILL.md)。**提交前**必须 `python -m forge check` 绿 **并且** 持有非空 `FORGE_SUBMIT_TOKEN`。路径：[`docs/dev-main-flow.md`](../../docs/dev-main-flow.md)。

## Instructions

1. **Local gate first.** 不绿则不 push、不开 PR。

```text
PYTHONPATH=../AIOps python3 -m forge check --root . --title "feat(overlay/agent): add cover triad"
```

有 `overlay.yaml` 时跑 validate + cover；pr-title 按事件取值（本地未设才 skip；`pull_request` 空白红；`push` lint HEAD 提交）；`docs_sync` / `suite_guard` / `deny_paths` 总会跑。工作本才跑 `sop-lock` / `schema` / 快单测。

2. **Open a draft PR onto `protect[0]`**（通常 `dev`）。`forge submit` 即使 `--dry-run` 也要 `FORGE_SUBMIT_TOKEN`。不要推保护分支。不要 merge。`--base` 必须在 `protect`。
3. **Do not live `forge apply`.** 不要改 Ruleset、required checks、产品仓已有的构建 workflow。
4. **Overlay：不要把 `status` 改成 `blocked`。** `suite_guard` 在 agent 分支上会红。人改走 `$manage-repo`。
5. **Title** 过 `python -m forge pr-title`。本工作本 `title.scopes` 是列表（`product/actor`）；接入方若写 `any` 则只查 Conventional Commits 语法。正文六节：`做了什么` `为什么` `动了哪些门` `怎么验` `不做什么` `分工`。进保护分支默认 squash：**封顶**再压，压完**换底**。
6. **Promote 不是 submit。** `dev` → `main` 用 `forge promote`，仍然不 merge。
7. 需要状态页时：`python -m forge status --repo OWNER/NAME --root . --write docs/STATE.md`。改 `forge/**` 时按 `docs_sync` 同步 CHANGELOG / 配置文档。

### Never

- 不要 vendor 工具。
- 不要 pin `main`。不要 force-move 旧针。
- 不要自 merge / 自批。
- 不要发明 `python -m forge brief|credential|ops-chain|revoke`。
- 不要在缺 `FORGE_SUBMIT_TOKEN` 时 submit。

## Examples

```text
git switch -c cursor/fix-slice
PYTHONPATH=../AIOps python3 -m forge check --root . --title "feat(overlay/agent): add cover triad"
PYTHONPATH=../AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(overlay/agent): add cover triad" --dry-run
```

非法：`git push origin main`。非法：check 红还 submit。非法：agent 分支写 `status: blocked`。

## Performance Notes

`forge check` 是本地的。Overlay 模型 token 不在 push 上花。

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想直推 main | 停。先 check，再 submit 到 `dev`。 |
| `forge check` 红了 | 停。按清单修。 |
| 缺 `FORGE_SUBMIT_TOKEN` | 停。不要用 `GITHUB_TOKEN` / `gh auth` 凑。 |
| 想合自己的 agent PR | 停。等人。 |
| `pr-title` 红了 | 改 PR 名。`title.scopes: any` 时不要句号、不要超过 72。 |
| `docs_sync` 红了 | 补 `require` 文件，或登记 CHANGELOG 段，或 `forge status --write`。 |
| 想从还没合进保护分支的旧头再开一单 | 停。封顶。squash 后换底。 |

## Lock（不绿不能合）

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

- **代推锁：** `python -m forge check` 必须绿 **并且** 持有非空 `FORGE_SUBMIT_TOKEN`。CI `GITHUB_TOKEN` 是合入锁，不是代推。
- 标题 + 正文六节 → **`pr-title`**。进保护分支默认 squash：**封顶**再压，压完**换底**。`submit` base 是 `protect`。
- Overlay 产品门仍是 **`overlay-check`**。仓级 SOP：`python -m forge sop-lock` → **`sop-lock`**。**通用检查 ≠ 产品门。** 不绿不能提交。不绿不能合。不要装 husky。不要自合。
