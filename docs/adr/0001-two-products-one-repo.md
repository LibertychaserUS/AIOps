# 0001 一个仓、两件产品

- 状态：已接受
- 日期：2026-09-11

## 背景

人 + agent 在 GitHub 上写同一仓时，缺两截能力：协作落地（谁能推、谁开 PR、检查绿了谁来合），以及需求叶子变成可审用例并按状态决定跑不跑。把它们揉成一只「万能云 agent」或门户，会把合入权、用例状态和构建门缠在一起。接入方已经有自己的构建门（CI job 名由产品仓决定），也不该被第二套构建替代。

## 决定

本工作本交付 **两件可独立安装的产品**，同仓发布、分 tag：

| 产品 | 管什么 | 不管什么 |
|---|---|---|
| **Forge** | 开发侧 `check` → `submit`（代推 draft PR）；Ops 侧按分支装 Ruleset；`promote` 开保护分支之间的 PR | 不合入；不改 Overlay `status`；不替代构建门 |
| **Overlay** | 需求 → 可审套件；`select` / `run` 只跑 `active`；`blocked` 丢掉且不当红 | 不管谁该 merge；不改接入方构建 workflow |

账本是接入方自己的 Git。工具源码（`forge/`、`overlay/`、`schema/`、`prompts/`）留在本工作本或 fork，不要 vendor 进产品仓。接入方可只装一件。发布用 `overlay-vX.Y.Z` 与 `forge-vX.Y.Z` 两条 tag，不要拿 GitHub Latest 当针。

现状（pin、保护分支、Ruleset 是否已装）见 [`docs/STATE.md`](../STATE.md)（由 `forge status --write` 生成）。

## 后果

- 文档、CI、skill 按产品前缀分治：同前缀可合，跨产品不合。通用检查（`pr-title` / `sop-lock`）≠ 产品门（`overlay-check` / `forge-check`）。工作本另有永远跑的 `unittest` job。
- 接入方 `required_checks` 必须填 PR 上真实的 **CI job 名**，不要抄别的仓的检查名。
- 两件产品失败独立：Overlay 红 ≠ Forge 红 ≠ 构建门红。

## 替代方案

- 做成门户 / 自建 RBAC / 数据库：否。协作面就是 GitHub。
- 焊成一只云 agent：否。Forge 不合入，Overlay 不改 Ruleset。
- 每个 Business Function 一个微服务：否。本仓是工具工作本，不是产品微服务网。
