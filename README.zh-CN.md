# AIOps

[English README](README.md)

这是 **Forge** 与 **Overlay** 的工具仓：一个仓、两件产品、两条 tag。都不部署。都不替代接入方已有的构建门。不要把 `forge/`、`overlay/`、`schema/`、`prompts/` 拷进产品仓。

**别的 agent：从本文件进。** 英文 [`README.md`](README.md) 只是一页入口。规则、契约、ADR、CHANGELOG 以中文为准。

需要 CPython **3.12+**。把本仓（或 fork）clone 到产品仓旁边。只 pin **已经存在的 tag 或 SHA**，不要 pin 浮动 `main`。不要 force-move 旧针。

**现状**（pin、保护分支、Ruleset、CI job 名）只看 [`docs/STATE.md`](docs/STATE.md)（`forge status --write` 生成，不要手写「当前 pin」）。CLI 只看 [`docs/cli.md`](docs/cli.md)，不要在别的文档里手抄子命令。

---

## 30 秒

1. **Forge** 管谁能推、谁开 PR、哪些路径不能改、哪些 **CI job 名**必须绿。它不合入。开发侧 `check` → `submit` 到 `protect[0]`（常见为 `dev`）；Ops 用 `promote` 开 `dev`→`main` PR；人批 + CODEOWNERS 后合；`release` 打产品 tag。
2. **Overlay** 管需求叶子变成可审套件。CI 跑 **`active`**。**`blocked`** 丢掉、不当红，且 `blocked_reason` 必须含链接或登记编号。人签走 PR 批准 + CODEOWNERS。见 [ADR 0002](docs/adr/0002-remove-armed.md)。
3. clone → checkout 已发布 tag → `pip install` → `PYTHONPATH` → 下面三条命令。

```text
git clone <本工作本> /tmp/AIOps
cd /tmp/AIOps
python3 -m pip install -r requirements.txt
export PYTHONPATH=/tmp/AIOps

cd /path/to/product
python3 -m overlay validate --root .
python3 -m overlay cover --root .
python3 -m forge check --root .
```

升级 1.0.x：[`docs/migration-v2.md`](docs/migration-v2.md)。设计：[`docs/design.md`](docs/design.md)。决定：[`docs/adr/`](docs/adr/)。变更：[`CHANGELOG.md`](CHANGELOG.md)。

Agent 可以 `check` / `submit`。Agent **不可以** live-`apply` Ruleset、自合、自批、改 `deny_paths`、把套件改成 `blocked`。

---

## 冷启动

开发：[`skills/use-forge/SKILL.md`](skills/use-forge/SKILL.md)（合入后为 v1.1：dev/main、`promote`、STATE、docs_sync）。Overlay：[`skills/use-overlay/SKILL.md`](skills/use-overlay/SKILL.md)。用例：[`skills/design-cases/SKILL.md`](skills/design-cases/SKILL.md)。

装 skill（host id：`codex` / `cursor` / `claude-code` / `github-copilot`）：

```text
gh skill install <owner>/<workshop> --agent cursor --pin overlay-v2.0.0 --all
```

或把 `skills/*` symlink 到 `.agents/skills` / `.cursor/skills` / `.claude/skills`。

**第一次 vs 之后默认跑。** Forge 是开发完成后的 GitHub 落地（`check` → `submit`），不是测试工具。接入方若已有自己的落地方式：先对照新旧（不合入、不 live-apply、不改构建门），等人明确同意再写 `forge.yaml`。同意过一次之后默认跑 `check` / `submit`。初始化同意 ≠ 可以 live-apply。

代推密钥：[`docs/submit-credential.md`](docs/submit-credential.md)。必须持有 `FORGE_SUBMIT_TOKEN`。`gh auth login` / `GH_TOKEN` / extraheader / `GITHUB_TOKEN` 都不够。Forge 不保管密钥。Overlay 的 `OPENAI_API_KEY` 是另一把（仅 generate）。

---

## Overlay 契约（避免假红）

叶子：

```markdown
## INV-01
### Functional
### Negative
### Edge
```

- 技法名只能是 Functional / Negative / Edge。不要写 `### Depth`。不要用散文 `##` 当标题。
- `function_id` 在 overlay root **全局唯一**。
- `invariants.yaml` 必须对上 `##` 标题。
- `status` 只有 `active` | `blocked`。隔离未就绪用 `blocked` + 带链接的 `blocked_reason`。人签走 PR 批准 + CODEOWNERS。见 [ADR 0002](docs/adr/0002-remove-armed.md)。

产品仓 CI：`uses: <workshop>/.github/workflows/overlay.yml@overlay-v2.0.0`，需要产品工具链就传 `setup_command`。**已经有能跑的 inline caller，不要换形状。**

`required_checks` 填 GitHub 上显示的 job 名。最小接入示例：[`examples/acme-python/`](examples/acme-python/)。

---

## 禁止

- 不要 vendor 工具包
- 不要 pin `main`，不要 force-move 旧 tag
- 不要改接入方构建 workflow，不要把旁路测试塞进构建门
- 不要 live-apply 到 `forbidden_live_repos` 里的仓
- 不要打接入方生产域名（`forbid_hosts` 只是字符串匹配，不是安全边界）
- 不要代签用例；不要把套件改成 `blocked`（agent 分支上 `suite_guard` 会红）
- 不要 push 时 `generate`
- 不要自 merge、自 Approve
- 不要把手抄 CLI 清单写进 skill；看 [`docs/cli.md`](docs/cli.md)

工作本入口：[`AGENTS.md`](AGENTS.md)。SOP 索引：[`docs/sop.md`](docs/sop.md)。
