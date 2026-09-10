# 代推需要写权限密钥；Forge 不保管，只消费宿主注入

一页说清：**密钥存在哪、谁注入、`forge submit` 怎么用、没有会怎样。**

Forge **不是**密钥库，也不是 GitHub 已经有的协作产品（`gh auth`、Actions secrets、Cursor 注入）的替代品。不要做 Forge vault，不要第二套权限库，不要让模型粘贴 PAT。

Overlay「token 只在人点 `generate`」是**另一把密钥**（模型 API：`OPENAI_API_KEY` / `OPENROUTER_API_KEY`）。那不是 GitHub 写权限，不是 `submit` 的凭证。不要混为一谈。

`forge apply` 的管理员钥匙（`FORGE_GITHUB_TOKEN`，Administration: write）也是另一把，只给 Ops 装 Ruleset。不是代推。

---

## 保存方式 / 使用方式

| Actor | 密钥存在哪（保存） | 谁注入 | submit 怎么用（使用） |
|---|---|---|---|
| 人，本机 | `gh auth login` → gh 凭据库 / OS keychain（`~/.config/gh`，**不在 git 仓里**） | 开发者自己登录一次 | `forge submit` 跑 `git push` + `gh pr create`，沿用这次登录。`gh auth status` 未登录则拒绝 |
| Cursor / 云代理 | Cursor GitHub App / 平台注入的 token（`GH_TOKEN` 或 git https `extraheader`）。活在 **agent 运行时**，不在 workshop git、不在 `overlay.yaml` / `forge.yaml`、不在聊天、不在回执 | 宿主（Cursor / 云平台），不是模型 | `forge submit` 用已经注入的 git/gh 凭证。git 和 gh 都不能认证则拒绝。**不要**向模型粘贴 PAT |
| CI Actions | job 权限里的 `GITHUB_TOKEN` | Actions | **合入锁**（check + merge），**不是代推**。overlay / pr-title / sop-lock workflow **不得**调用 `forge submit` |

禁止：

- 把 token、`.env`、Forge 密钥文件提交进 git
- 打印 token
- 把 token 写进 PR 正文 / 回执 / traces / suite yaml
- 发明第二把 Forge 专用提交环境变量当产品故事
- 自动合入、自 Approve、直推保护默认分支

---

## 没有密钥时的行为

`python -m forge submit`（**包括 `--dry-run`**）fail-closed：

1. 探测宿主写权限（只报有无和来源名：`gh-login` / `GH_TOKEN` / `git-extraheader`，**不打印值**）。
2. 没有可用写权限 → 退出码 `2`，不 push、不开 PR。`--dry-run` 同样失败。
3. 有凭证再跑 `python -m forge check`。本地 check 红 → 退出码 `2`，不 push、不开 PR。
4. 都过：`--dry-run` 打印计划后退出 `0`；live 则 `git push` 功能分支 + `gh pr create`（已有则更新）开 **draft** PR。永不 merge，永不 `apply` Ruleset，永不推 protect / `main`。

CI 里 `GITHUB_ACTIONS=true` 时，submit 一律视为没有代推凭证（`GITHUB_TOKEN` 不是代推钥匙）。

---

## 一条命令

开发者本地（先 `gh auth login` 一次）：

```text
python3 -m forge check --root . --title "feat(forge/dev): subject"
python3 -m forge submit --repo OWNER/NAME --title "feat(forge/dev): subject"
```

云代理（宿主已注入 `GH_TOKEN` 或 extraheader；不要向模型要 PAT）：

```text
python3 -m forge check --root . --title "feat(forge/agent): subject"
python3 -m forge submit --repo OWNER/NAME --title "feat(forge/agent): subject"
```

对照：[`design.md`](design.md) §3.4、[`rbac.md`](rbac.md)、[`../skills/dev-pr/SKILL.md`](../skills/dev-pr/SKILL.md)。
