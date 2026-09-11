# AIOps

[English README](README.md)

这是 Forge 和 Overlay 的**工具仓**，不是 Learning Guide 产品仓，也不是 First-Light 那个空的 `AIOps`。一个仓、两件产品。都不部署。都不替代接入方已有的构建门（Learning Guide 的 Verify 是这条规则的第一个例子）。

**别的 agent：从本文件或 [README.md](README.md) 进。** 只 pin **已经打在 GitHub 上的 tag**。不要 pin 浮动 `main`。不要把 `forge/`、`overlay/`、`schema/`、`prompts/` 拷进产品仓。

| 产品 | 现在能 pin 的 tag | SHA | 管什么 |
|---|---|---|---|
| **Overlay** | [`overlay-v1.0.0`](https://github.com/LibertychaserUS/AIOps/releases/tag/overlay-v1.0.0) | `235e514e673fa68b24879c8e139f2a5c6633ebb5` | 需求叶子 → 可审套件。CI 只跑 `armed`。没有 `generate`。 |
| **Forge** | [`forge-v1.0.0`](https://github.com/LibertychaserUS/AIOps/releases/tag/forge-v1.0.0) | 同一 SHA | 本地 `check` 绿之后 `submit` 开 draft PR。人 + Ruleset 才合。Forge 不合入。 |

`main` 上的 `pyproject.toml` 可能已经写着 `1.0.1`。**`overlay-v1.0.1` / `forge-v1.0.1` 这两个 tag 现在不存在。** 人按 [`docs/release.md`](docs/release.md) 发布之前，agent 必须 pin **v1.0.0**。禁止 `git checkout overlay-v1.0.1`。禁止 pin `main`。GitHub 的 Latest 徽章只挂一件产品，不要拿 Latest 当针。

需要：CPython **3.12+**。把本仓（或 fork）clone 到**产品仓旁边**。

---

## 30 秒

1. **Forge** 管谁能推、谁开 PR、哪些路径不能改、哪些 **CI job 名**必须绿。它不合入。
2. **Overlay** 管需求叶子变成可审套件。CI 只跑 **`armed`**。`draft` / `blocked` 丢掉、不当红。
3. clone → checkout **已存在的 tag** → `pip install` → `PYTHONPATH` → `forge check` / `overlay validate`。
4. Agent 可以 `check` / `submit`。Agent **不可以** live-`apply` Ruleset、填 `reviewed_by`、把套件改成 `armed`。

---

## 冷启动（产品仓旁边）

```text
git clone https://github.com/LibertychaserUS/AIOps.git /tmp/AIOps
cd /tmp/AIOps
git checkout overlay-v1.0.0
python3 -m pip install -r requirements.txt
export PYTHONPATH=/tmp/AIOps

cd /path/to/product
python3 -m overlay validate --root .
python3 -m overlay cover --root .
python3 -m forge check --root .
```

`overlay-v1.0.0` 和 `forge-v1.0.0` 是同一提交。checkout 哪一条都行。

`python -m forge` 现有子命令：`apply` `status` `check` `submit` `pr-title`/`title` `sop-lock` `ci-select` `ops-review` `bounce` `release`。没有 `brief`、`credential`、`ops-chain`、`revoke`。

| 动作 | 谁做 |
|---|---|
| `forge check` | Agent 可以 |
| `forge submit` | Agent 可以，且必须有 `FORGE_SUBMIT_TOKEN`（见 [`docs/submit-credential.md`](docs/submit-credential.md)） |
| live `forge apply` | **不可以**（Ops；[`skills/manage-repo/SKILL.md`](skills/manage-repo/SKILL.md)）。Learning Guide **现在不做** |
| 写 `reviewed_by` / 改 `armed` | **不可以**（人审） |

开发冷启动六步：[`skills/use-forge/SKILL.md`](skills/use-forge/SKILL.md)。Overlay 契约：[`skills/use-overlay/SKILL.md`](skills/use-overlay/SKILL.md)、[`skills/design-cases/SKILL.md`](skills/design-cases/SKILL.md)。

**第一次 vs 之后默认跑。** Forge 是开发完成后的全栈 GitHub 落地（`check` → `submit`），不是测试工具。不要为了接 Forge 去改 Overlay / Verify。接入方如果已有 `gh pr create`、husky、直推 main、只走 Verify、或自己的分支名：先提醒对照新旧（不合入、不 live-apply、不 arm、不改 Verify），等人明确同意再写 `forge.yaml` / 贴政策。同意过一次——或仓里已有 `forge.yaml` 且他们说过「同意」——之后只再问一次，说「之后默认按 Forge 落地」，然后默认跑 `check` / `submit`。不要每次存盘都问。初始化同意 ≠ 可以 live-apply 或 arm Overlay。

别的 agent 装 skill（只 pin **已存在的 tag**；`gh skill` 没有 `--agent copilot`）：

```text
gh skill install LibertychaserUS/AIOps --agent codex --pin overlay-v1.0.0 --all
gh skill install LibertychaserUS/AIOps --agent cursor --pin overlay-v1.0.0 --all
gh skill install LibertychaserUS/AIOps --agent claude-code --pin overlay-v1.0.0 --all
```

或在产品仓把 `skills/*` symlink 到 `.agents/skills` / `.cursor/skills` / `.claude/skills`。`overlay-v1.0.0` 上的 `use-forge` 仍把 `apply` 写进安装步骤；冷启动以本 README / 本仓更新后的 `use-forge` 六步为准，live `apply` 只在 `manage-repo`。

---

## Overlay 契约（避免 `forge check` 假红）

`cases.md` 叶子必须是：

```markdown
## AUTH-01
### Functional
### Negative
### Edge
```

- `###` 技法名只能是 **Functional / Negative / Edge**（大小写不敏感）。不要写 `### Depth`。
- 不要用 `## Specified / not tested now` 当标题：`##` 的第一个无空白词会被当成 `function_id`。
- `function_id` 在整个 overlay root **全局唯一**，不要跨套件复用。
- `invariants.yaml` 的 `function_ids` 必须对上某篇 `cases.md` 的 `##` 标题；invariant id 必须在某篇 `cases.md` 里作为独立 token 出现。
- 本工作本 fixture 里 login/payment 是 **blocked**。Learning Guide 产品仓可能已经 **armed**。不要把 fixture 状态抄到产品上。

产品仓 CI：可以 `uses: LibertychaserUS/AIOps/.github/workflows/overlay.yml@overlay-v1.0.0`，也可以自己写 inline `overlay-check.yml`（checkout pin 再跑 CLI）。**产品仓已经有能跑的 inline，就不要再抄 reusable。**

`required_checks` 填 **GitHub 上显示的 check / job 名**，不要抄 workflow 的 `name:`，除非两个字符串本来就一样。例子里的 `Verify` 只是例子。Learning Guide 是 `Typecheck` / `Lint` / `Build and test` / `overlay-check`。

---

## 禁止

- 不要 vendor `forge/` / `overlay/` / `schema/` / `prompts/`
- 不要 pin `main`，不要 checkout 不存在的 `v1.0.1`
- 不要改 Learning Guide Verify，不要把 `test:io` 塞进 Verify
- 不要 live-apply Forge 到 LearningGuidePortal
- 不要打 `ilovelearningguide.com`
- 不要代签 `reviewed_by` / `armed`
- 不要 push 时 `generate`
- 不要自 merge、自 Approve
- 不要把 Harness MCP 的 pipeline skill 当成这套 Forge

细设计在 [`docs/design.md`](docs/design.md)，不要把那一篇整篇搬进产品仓。
