# 0007 提交内容包按层配对

- 状态：提议
- 日期：2026-09-12

## 背景

接入方问：每次提交是不是都要同时交文档、代码、CI workflow。如果写成「每单三件套」，agent 在产品仓改 `.github/workflows/` 会被 `deny_paths` 红；把升针塞进功能切片，合入锁和产品改动绑死（空 `PR_TITLE` 的 push 红就是这一类）。

`docs_sync`（[0005](0005-docs-sync-and-state.md)）、`deny_paths`、CI workflow 是先实现再补说明的。当时只锁了「改这些路径要带文档」「agent 不许碰 workflow」，**没有先定义一单内容包是什么、三层各算谁的包**。这是一开始漏掉的设计。本条是补设计，不是已经接受的实现。

## 顺序

新的合入 / 内容包规则：

1. 先写 ADR + 入口文档 + 登记（本工作本 `docs/`，产品仓 brief / OF）。
2. 人接受（把本条改成「已接受」）。
3. 再改 `forge.yaml` / CLI / workflow / 测试。

不要先写锁再补说明。本条未接受之前，**不加**新的 `docs_sync` 行，不改 CLI，不改产品仓 `.github/workflows/`。已经在跑的 `docs_sync` / `deny_paths` / `status --check-state` 先维持，不当成本条的实现完成。

## 决定（提议）

1. **内容包 = 进保护枝的 squash PR**，不是功能枝上每一颗 WIP。
2. **按层配对，不是三件套。** 碰哪一层，同单带那一层的配对物；没碰的层不要塞进来。
3. **四层：**
   - 代码（产品或 `forge/**` / `overlay/**`）→ `docs_sync` 表里的 `require`
   - 解说（PR 标题 + 六个 `##`）→ `pr-title` / `pr-body`；正文从 diff 写
   - 生成现状（`docs/STATE.md`）→ 配置 / job 名 / protect 变了才 `forge status --write`
   - CI workflow → **人 / Ops 的独立包**；产品仓把 `.github/workflows/` 放进 `deny_paths` 时 agent 不得改
4. **五种包：** 产品包、工具包、文档包、工作流 / 升针包、升级包（`promote`）。升针等对应 tag 先发布，再单独改 workflow，不要夹功能。
5. **不写**「每个 agent PR 必须改 workflow」。那不是覆盖，是卸 `deny_paths` 或让每单都红。

## 后果（接受之后）

- 现有 `docs_sync` 继续只锁「命中 paths 必须改 require」，不负责把 workflow 塞进每单。
- 要不要给升针文件加一条 `docs_sync` → 入口文档：接受本条之后再加，不提前写进 `forge.yaml`。
- 产品仓升针是 Ops 包：改 `*-check.yml` 的 pin、同步入口文档、必要时重写 STATE。
- 审查看两件事：正文是否描述了 diff；这一单是否只装了该装的层。

## 替代方案

- 每单强制文档 + 代码 + workflow：否。和 `deny_paths` 打架，也制造升针与功能的鸡生蛋。
- 把 `deny_paths` 改成 advisory：否。agent 不得改合入锁形状。
- 先加锁、设计后补：否。这就是本条要停的做法。
