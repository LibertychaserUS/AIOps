# 代推必须持有 `FORGE_SUBMIT_TOKEN`

开发侧代理提交（`python -m forge submit`，含 `--dry-run`）必须显式持有 **`FORGE_SUBMIT_TOKEN`**（PAT / fine-grained / GitHub App token）。缺或空：退出码 2（fail closed）。

**Forge 不保管** 这把密钥：不写进 git、不写进 `forge.yaml`、不写进回执。程序只读环境变量名 `FORGE_SUBMIT_TOKEN`，永不打印值。

这不是「只靠 git + gh」。本机 `gh auth login`、平台注入的 `GH_TOKEN`、git https extraheader、CI `GITHUB_TOKEN`、Ops 的 `FORGE_GITHUB_TOKEN` **都不够**。

Overlay「token 只在人点 `generate`」是**另一把密钥**（模型 API：`OPENAI_API_KEY` / `OPENROUTER_API_KEY`）。那不是 GitHub 写权限，不是 `submit` 的凭证。不要混为一谈。

`forge apply` 的管理员钥匙（`FORGE_GITHUB_TOKEN`，Administration: write）也是另一把，只给 Ops 装 Ruleset。不是代推。Ops merge 用 GitHub 写权限 + Ruleset，不是这把提交密钥。

`promote` 与 `submit` 同一把 `FORGE_SUBMIT_TOKEN`。

子命令：[`cli.md`](cli.md)。RBAC：[`rbac.md`](rbac.md)。对照：[`design.md`](design.md)。

---

## 保存 / 使用

| Actor | 必须持有 | 不是这个 |
|---|---|---|
| 人 / agent 本机或云 | 环境变量 `FORGE_SUBMIT_TOKEN`（运行时注入，不进 git） | `gh auth login`、`GH_TOKEN`、git extraheader、`GITHUB_TOKEN` |
| CI overlay-check / forge-check | 工作流本身不得 live-submit。单测用假值证明密钥名 | job 的 `GITHUB_TOKEN`（合入锁，不是代推） |

禁止：

- 把 token、`.env`、真实密钥提交进 git
- 打印 token
- 把 token 写进 PR 正文 / 回执 / traces / suite yaml
- 用 `gh auth` 或 CI `GITHUB_TOKEN` 冒充代推产品故事
- 自动合入、自 Approve、直推保护分支、live-apply Rulesets

---

## 没有密钥时的行为

1. 先跑本地 `python -m forge check`。红 → 退出 2，不 push。check 不读密钥。
2. 再要求 `FORGE_SUBMIT_TOKEN`。缺或空 → 退出 2，打印 `would require FORGE_SUBMIT_TOKEN` / `missing FORGE_SUBMIT_TOKEN`。`--dry-run` 同样红。
3. 都过：`--dry-run` 打印计划后退出 0；live 则同一把 `FORGE_SUBMIT_TOKEN` 注入 HTTPS extraheader 推功能分支，并开/更新 **draft** PR。本机已有 extraheader 不是凭证。永不打印 token。永不 merge，永不 approve，永不 apply Ruleset。
