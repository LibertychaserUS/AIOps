# AIOps

工作本入口。两件产品：**Forge**（GitHub 落地）与 **Overlay**（可审用例 + 按状态跑）。不是某一家业务仓。

1. **规则** — 不要 pin 浮动 `main`。不要 vendor `forge/` / `overlay/`。不要 live-apply Ruleset（Ops / `$manage-repo`）。不要自合、自批。不要改接入方构建 workflow。不要打生产域名。Overlay 状态只有 `active` | `blocked`；人签走 PR 批准 + CODEOWNERS。Agent 不要把套件改成 `blocked`。中文权威；英文只留根 README 一页。
2. **现状** — [`docs/STATE.md`](docs/STATE.md)（`forge status --write` 生成）。不要在本文件或设计文档里手写 pin / Ruleset / job 名。
3. **登记 / ADR** — [`docs/adr/`](docs/adr/)、[`CHANGELOG.md`](CHANGELOG.md)、[`docs/migration-v2.md`](docs/migration-v2.md)、[`docs/design.md`](docs/design.md)。CLI：[`docs/cli.md`](docs/cli.md)。
4. **Skills** — [`skills/use-forge/SKILL.md`](skills/use-forge/SKILL.md)、[`skills/use-overlay/SKILL.md`](skills/use-overlay/SKILL.md)、[`skills/design-cases/SKILL.md`](skills/design-cases/SKILL.md)、[`skills/dev-pr/SKILL.md`](skills/dev-pr/SKILL.md)、[`skills/manage-repo/SKILL.md`](skills/manage-repo/SKILL.md)。索引：[`docs/sop.md`](docs/sop.md)。发现路径：`.agents/skills/`、`.cursor/skills/`、`.claude/skills/`。

代推：`python -m forge check` 必须绿，且持有 `FORGE_SUBMIT_TOKEN`（[`docs/submit-credential.md`](docs/submit-credential.md)；`gh auth` 不够），才能 `submit`。PR 标题过 `pr-title`（工作本 scope 见 `forge.yaml` `title.scopes`）。正文六节见 [`docs/pr-brief.md`](docs/pr-brief.md)。进保护分支 **squash 封顶**，合完 **换底**。

**通用检查 ≠ 产品门。** `pr-title` / `sop-lock` 永远跑；工作本 `unittest` 永远跑。产品门按分支 `required_checks`。程序锁：`python -m forge sop-lock`（不绿不能合）。
