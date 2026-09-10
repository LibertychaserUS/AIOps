<!--
解说规格：docs/pr-brief.md

PR 名（标题）前缀是唯一的分工标记。两个方括号 + 空格 + 一句动词：
  [<role>][<product>] <imperative>
role:    管理 | 开发 | agent
product: Forge | Overlay | CI | docs
例: [开发][Overlay] add overlay run to overlay-check

不是分支名、不是 workflow 名、不是 skill 名。
不要改 cursor/…-6842 或 copilot/ 分支前缀。
不要改成 feat(overlay/dev): … 或新开 pr-title workflow。

六个二级标题必须原样保留，便于 grep。
正文「分工」写谁审 / 谁合（人，见 docs/rbac.md），不是标题前缀。
开发写，管理拒收：标题无此前缀，或缺任一节。
-->

## 做了什么

<!-- 列表。混改逐条写。 -->

-

## 为什么

<!-- 契约 / git-chain：design.md、对话整理、状态机、Ruleset。 -->

-

## 动了哪些门

<!-- overlay-check | Forge Ruleset | none。不要为未知分支新建 workflow；改 overlay.yaml branches。 -->

-

## 怎么验

<!-- 命令 + 哪些 armed suite 应入选 / 哪些 draft|blocked 应丢弃。 -->

```text

```

## 不做什么

<!-- Verify / Proctor / Deepseek3 / generate on push / live forge apply / 生产 / vendor / 门户 -->

-

## 分工

<!-- 谁审、谁可合。人，不是标题前缀。对照 docs/rbac.md。Agent 不自审、不自合。 -->

- 审：
- 合：
