<!--
解说规格：docs/pr-brief.md

PR 标题必须过 python -m forge pr-title（Conventional Commits）。
这是唯一的分工标记：
  type(product/actor): subject
type:    build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test
product: forge|overlay|ci|docs   （也选产品门：overlay/forge 各一；ci=两门；docs=只跑通用）
actor:   dev|admin|agent   （开发=dev，管理=admin）
例: feat(overlay/dev): add overlay run to overlay-check
通用检查 ≠ 产品门。pr-title / sop-lock 永远跑。overlay-check / forge-check 由 forge.yaml ci 选跑或跳过。

进 main 默认 squash：这一单必须是整段工作的封顶。合完从 main 新 SHA 换底再开下一枝。不要把未合的 cursor/ 旧头当 base。

不是分支名、不是 workflow 名、不是 skill 名。
不要写 [开发][Overlay]。不要用 dev feat(overlay):。
不要改 cursor/…-6842 或 copilot/ 分支前缀。

六个二级标题必须原样保留，便于 grep。
正文「分工」写谁审 / 谁合（人，见 docs/rbac.md），不是标题 actor。
开发写，管理拒收：pr-title 红，或缺任一节。
-->

## 做了什么

<!-- 列表。混改逐条写。 -->

-

## 为什么

<!-- 契约 / git-chain：design.md、对话整理、状态机、Ruleset。 -->

-

## 动了哪些门

<!-- 通用 pr-title / sop-lock（永远跑）| 产品 overlay-check / forge-check（forge.yaml ci 选跑或跳过）| Forge Ruleset | none。不要为未知分支新建 workflow；改 overlay.yaml branches。 -->

-

## 怎么验

<!-- 命令 + 哪些 armed suite 应入选 / 哪些 draft|blocked 应丢弃。 -->

```text
python3 -m forge check --root . --title "feat(overlay/dev): …"
python3 -m forge sop-lock --root .
python3 -m forge pr-title --title "feat(overlay/dev): …"
python3 -m forge ci-select --check overlay-check --title "feat(overlay/dev): …"
```

## 不做什么

<!-- Verify / Proctor / Deepseek3 / generate on push / live forge apply / 生产 / vendor / 门户 / 强制 husky -->

-

## 分工

<!-- 谁审、谁可合。人，不是标题 actor。对照 docs/rbac.md。Agent 不自审、不自合。通用检查 ≠ 产品门。红则不合。 -->

- 审：
- 合：
