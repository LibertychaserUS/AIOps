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
