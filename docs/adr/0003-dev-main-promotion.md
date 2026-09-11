# 0003 保护分支晋升（dev → main）

- 状态：已接受
- 日期：2026-09-11

## 背景

v1 的 `submit` 默认 base 是 `protect`（常常只有 `main`）。Agent 开 draft PR 直接对着主干，合入要人批，但「集成枝」和「发布枝」没有分开。人多了以后，希望：agent 落到第一条保护分支（CI 要绿、无人批），再由人把该枝晋升到第二条保护分支（要批 + CODEOWNERS）。Forge 仍然不合入。

## 决定

走 **A 路线**（全图见合入后的 `docs/dev-main-flow.md`）：

```text
agent 功能枝
    │  forge check 绿 + FORGE_SUBMIT_TOKEN
    ▼
forge submit  →  开/更新 draft PR，base = protect[0]（默认 dev）
    │  CI required（按该分支规则）；approvals: 0
    ▼
人 merge 进 dev（merge commit；Ruleset 执行）
    │
    ▼
forge promote --from dev --to main
    │  已有 open PR 则更新标题/正文，否则创建（非 draft）
    │  标题 chore(release/agent): promote dev → main (<short sha>)
    │  永不 merge
    ▼
人批准（1）+ CODEOWNERS 后 merge 进 main
    │
    ▼
forge release 打 overlay-v* / forge-v* tag（人点，不是 push 自动发）
```

- `submit --base` 必须落在 `protect` 里。
- `promote` 与 `submit` 共用 `FORGE_SUBMIT_TOKEN`。
- 进保护分支的 PR 仍是整段工作的 **squash 封顶**；合完以目标枝新 SHA **换底**再开下一枝。不要从即将被压掉的旧头再叠。
- 人与 agent：agent 可以 `check` / `submit`；不可以 live `apply`、自合、自批、改 `deny_paths`、把套件改成 `blocked`。人 / Ops 才 `apply`、勾 Ruleset、`promote` 之后点 merge、`release`。

## 后果

- `forge.yaml` `protect` 的第一项是 submit 默认 base。工作本与接入示例用 `dev` 然后 `main`。
- 接入方若只有一条保护分支，`protect: [main]` 仍合法；没有 `promote_from` 就不走晋升。
- Graphite stack / merge-when-ready 不做。Forge 永不 merge。

## 替代方案

- Agent 直推 `dev`：否。仍必须 PR。
- `promote` 自动 merge：否。人点。
- 用 GitHub Merge Queue 当第一刀：以后由接入方在同一 Ruleset 上打开，默认关。
