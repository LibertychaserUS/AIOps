<!--
解说规格：docs/pr-brief.md
CLI：docs/cli.md
标题必须过 python -m forge pr-title。
工作本 scope 见 forge.yaml title.scopes（type(product/actor): subject）。
通用检查 ≠ 产品门。pr-title / sop-lock / unittest 永远跑。产品门按分支 required_checks。

进保护分支默认 squash：这一单必须是整段工作的封顶。合完从目标枝新 SHA 换底再开下一枝。
不要把未合的 agent 枝旧头当 base。
-->

## 做了什么

<!-- 列表。混改逐条写。 -->

-

## 为什么

<!-- 契约 / git-chain：design.md、ADR、状态机、Ruleset。 -->

-

## 动了哪些门

<!-- 通用 pr-title / sop-lock / unittest（永远跑）| 产品 overlay-check / forge-check（按分支）| Forge Ruleset | none。不要为未知分支新建 workflow；改 overlay.yaml branches。 -->

-

## 怎么验

<!-- 命令 + 哪些 active suite 应入选 / 哪些 blocked 应丢弃。 -->

```text
python3 -m forge check --root . --title "feat(docs/agent): …"
python3 -m forge sop-lock --root .
```

## 不做什么

<!-- 构建门 / generate on push / live forge apply / 生产 / vendor / 门户 -->

-

## 分工

<!-- 谁审、谁可合。人，不是标题 actor。对照 docs/rbac.md。Agent 不自审、不自合。红则不合。 -->

- 审：
- 合：

---

## 文档勾选

- [ ] 文档：改动的契约已写进中文权威页（或 `docs/cli.md` 已重生成），相对链接能打开
- [ ] ADR：行为/状态机/合入规则变了则新增或改 `docs/adr/`
- [ ] CHANGELOG：产品行为变了则登记 `## [overlay-X.Y.Z]` 或 `## [forge-X.Y.Z]`
