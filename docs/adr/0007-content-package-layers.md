# 0007 提交内容包按层配对

- 状态：已接受
- 日期：2026-09-12

## 背景

接入方问：每次提交是不是都要同时交文档、代码、CI workflow。如果写成「每单三件套」，agent 在产品仓改 `.github/workflows/` 会被 `deny_paths` 红；把升针塞进功能切片，合入锁和产品改动绑死（空 `PR_TITLE` 的 push 红就是这一类）。

`docs_sync`（[0005](0005-docs-sync-and-state.md)）已经锁「碰了这些路径必须带配对文档」。缺的是一层设计：什么构成一单内容包，谁允许碰 workflow。

## 决定

1. **内容包 = 进保护枝的 squash PR**，不是功能枝上每一颗 WIP。
2. **按层配对，不是三件套。** 碰哪一层，同单带那一层的配对物；没碰的层不要塞进来。
3. **四层：**
   - 代码（产品或 `forge/**` / `overlay/**`）→ `docs_sync` 表里的 `require`
   - 解说（PR 标题 + 六个 `##`）→ `pr-title` / `pr-body`；正文从 diff 写
   - 生成现状（`docs/STATE.md`）→ 配置 / job 名 / protect 变了才 `forge status --write`
   - CI workflow → **人 / Ops 的独立包**；产品仓把 `.github/workflows/` 放进 `deny_paths` 时 agent 不得改
4. **五种包：** 产品包、工具包、文档包、工作流 / 升针包、升级包（`promote`）。升针等对应 tag 先发布，再单独改 workflow，不要夹功能。
5. **不写**「每个 agent PR 必须改 workflow」。那不是覆盖，是卸 `deny_paths` 或让每单都红。

## 后果

- `docs_sync` 继续只锁「命中 paths 必须改 require」，不负责把 workflow 塞进每单。
- 产品仓升针是 Ops 包：改 `*-check.yml` 的 pin、同步入口文档、必要时重写 STATE。
- 审查看两件事：正文是否描述了 diff（产品仓 OF-21）；这一单是否只装了该装的层（本条）。

## 替代方案

- 每单强制文档 + 代码 + workflow：否。和 `deny_paths` 打架，也制造升针与功能的鸡生蛋。
- 把 `deny_paths` 改成 advisory：否。agent 不得改合入锁形状。
