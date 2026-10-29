# 0008 tag 创建锁

- 状态：提议
- 日期：2026-10-29

## 背景

`forge-protected-tags`（[0004](0004-per-branch-rulesets.md)）对 `refs/tags/overlay-v*` / `refs/tags/forge-v*` 锁了 `update`、`deletion`、`non_fast_forward`，**没有** `creation`。任何有 write 权限的人（含拿到 `contents: write` 的 workflow）都能直接 `git push origin forge-vX.Y.Z`（一条没人发布过的版本），接入方 pin 到一条没人发布过的针。`forge release` 查 CHANGELOG、`__version__`、已有 Release，但 Ruleset 不挡绕过 `release` 的手推。

按「新的合入规则先写 ADR，后实现」：加锁先提议。提议未接受前，不能加默认开的新锁。

## 决定（提议）

1. `forge.yaml` 加 `tag_rules.creation`（bool，默认 **`false`**）。为 `true` 时 tag Ruleset 多一条 `{"type": "creation"}`。
2. 同时写一条 `bypass_actors`：`{actor_id: 5, actor_type: RepositoryRole, bypass_mode: always}`（仓库 admin），让 admin 跑 `forge release` 仍能打 tag。Forge 只在这里写 bypass；分支 Ruleset 的 `bypass_actors` 仍是 `[]`。
3. 现在是 opt-in。人接受本条之后，在下一个 **major**（`forge-2.0.0`）把默认改成 `true`，并在 CHANGELOG `### Changed` 登记。
4. 工作本自己的 `forge.yaml` 本条接受前不开。

## 后果

- 开了之后，`forge release`（本地或 `release.yml` 的 `workflow_dispatch`）必须用 admin 的 token；`GITHUB_TOKEN` 或普通 write 成员推 tag 会被 Ruleset 拒。要让 CI 发布，改为把发布 App 的 id 写进 `bypass_actors`（`actor_type: Integration`）——那是接受后再加的字段，本条不实现。
- `status` 比 `bypass_actors`：开关两边都要重新 `apply`，否则报 drifted。
- `deletion` / `update` / `non_fast_forward` 不变；关着时 tag Ruleset 与今天一样。

## 替代方案

- 直接默认开：否。违反「提议未接受不加默认锁」，也会立刻卡住用普通 token 发布的接入方。
- 只靠 `forge release` 的检查：否。它挡不住绕过 CLI 的 `git push --tags`。
- 用 GitHub 环境（environments）审批发布：可以叠加，但不是 Ruleset 层的事，且接入方未必有。
