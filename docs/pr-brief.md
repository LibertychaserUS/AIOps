# PR 解说规格

GitHub PR 是解说面。DevOps 和其他 agent 读**标题 + 正文**就知道做了什么，不靠翻 diff。不是门户，不另做解说站。

「分工」写在 **GitHub PR 标题** 的 Conventional Commits scope（`product/actor` 的 `actor`）。只这一处。不是分支名，不是 workflow 的 `name:`，不是 `skills/<name>/`。不要另造 `管理/`、`开发/`、`agent/` 分支前缀。Forge 已有的 `agent_branch_prefixes`（默认 `cursor/`、`copilot/`，如 `cursor/overlay-architecture-6842`）管谁的分支能推，不是本规格；这类分支名不要改。

标题 `actor` 只标明这单活戴哪顶帽子；`product` 标明碰哪件产品。谁审、谁合仍是 GitHub 上的人 + Ruleset，见 [`rbac.md`](rbac.md)。不要把标题当成权限。

开 PR 用 [`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)。开发写规格。管理拒收：`pr-title` 红，或正文缺下面任一稳定标题。开发端：[`../skills/dev-pr/SKILL.md`](../skills/dev-pr/SKILL.md)。管理端：[`../skills/manage-repo/SKILL.md`](../skills/manage-repo/SKILL.md)。

本地锁（程序，无模型、不写 GitHub）：

```text
python -m forge check --root . --title "feat(overlay/dev): add cover triad and invariants"
python -m forge pr-title --title "feat(overlay/dev): add cover triad and invariants"
```

退出 `0` 绿、`2` 红。CI 同名检查 **`pr-title`**（只跑 `pull_request`）。本工作本 `forge.yaml` `required_checks` 已列入 `overlay-check`、`pr-title`、`sop-lock`；Ruleset 勾上之后，红则不能合。代推前 `python -m forge check` 红则不能提交。不要 live `forge apply`。不要用 husky/npm 挡 `git commit`。

本仓 PR #3 的 GitHub 标题必须改成下面这一行（Agents 的 GitHub write 会 404，需要人在 UI 改名）：

```text
feat(overlay/agent): adopt Overlay CI and Conventional Commit PR titles
```

（若这单以 Forge submit 为主，也可用 `feat(forge/dev): add submit middleware and lock the Forge/Ops split`。不要另造第二种语法。）

---

## PR 名（标题）前缀

对齐 **[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)** 的 header：`type(scope): description`，可选 `!` 表示 breaking。类型枚举取 [Angular 贡献约定](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit) + [@commitlint/config-conventional](https://github.com/conventional-changelog/commitlint/tree/master/%40commitlint/config-conventional)（`chore` / `revert`）。PR 标题中间件对齐 [amannn/action-semantic-pull-request](https://github.com/amannn/action-semantic-pull-request)（`requireScope: true`）和 commitlint 的 `commit-msg` 锁，但**实现是 CPython**：`python -m forge pr-title` + Actions job `pr-title`。本工作本内核不引入 Node/husky/lefthook。Danger JS/Python 能做更宽的 PR lint，这里只锁标题，用不上。

不另造 `[开发][Overlay]` 或 `dev feat(overlay):`。后者不是 Conventional Commits，commitlint / amannn 都会红。分工（actor）放进 **scope**：`product/actor`。官方 parser 允许 scope 含 `/`。

```text
type(product/actor): subject
```

程序锁住的正则（`forge/title.py` `TITLE_PATTERN`，整行 `fullmatch`）：

```text
^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)\((forge|overlay|ci|docs)/(dev|admin|agent)\)!?: \S.*$
```

另：必须单行；首尾不得空白。

| 槽 | 取值 | 写什么 |
|---|---|---|
| `type` | `build` \| `chore` \| `ci` \| `docs` \| `feat` \| `fix` \| `perf` \| `refactor` \| `revert` \| `style` \| `test` | Angular / commitlint conventional。小写 |
| `product` | `forge` \| `overlay` \| `ci` \| `docs` | 主产品。混改写在「做了什么」，不要叠第二个产品 |
| `actor` | `dev` \| `admin` \| `agent` | 这单戴哪顶帽子。映射：开发端=`dev`，管理端=`admin`，agent=`agent` |
| `!` | 可选 | Conventional Commits breaking，紧贴 `)` 与 `:` |
| `subject` | 非空、不以空白开头 | 祈使、一事。不要散文标题 |

例：

- `feat(overlay/dev): add cover triad and invariants`
- `feat(overlay/dev): add overlay run to overlay-check`
- `docs(docs/admin): add PR brief spec`

合法：分支仍叫 `cursor/fix-armed-select`，标题写成 `fix(overlay/dev): fix armed select`。  
非法：把分支改成 `开发/overlay-fix` 来表示角色。非法：把 `overlay-check` 或 `dev-pr` 改名来表示角色。非法：`[开发][Overlay] fix armed select`。

混改：标题只标主产品。其余列在「做了什么」。不要写成 `feat(overlay+docs/dev):`。

可选本地包装（不默认安装 git hook）：`forge/hooks/pr-title "feat(overlay/dev): …"`；提交前整门：`forge/hooks/pre-submit --title "…"`。代推锁是 `python -m forge check`。合并锁是 GitHub 上的 `pr-title` check，不是本机 hook。

---

## 正文（稳定标题，便于 grep）

六个二级标题必须**原样**出现（与模板一致）。不要改名、不要翻译掉中文、不要换序。

```text
## 做了什么
## 为什么
## 动了哪些门
## 怎么验
## 不做什么
## 分工
```

### 做了什么

改了什么、交付什么。混改写成列表，不要散文。

### 为什么

对照哪条契约或 git-chain：[`design.md`](design.md)、[`2026-09-10-对话整理.md`](2026-09-10-对话整理.md)、Overlay `function_id` / 状态机、Forge Ruleset。一句话到一小段。

### 动了哪些门

只许这些值（可并列）：

| 值 | 含义 |
|---|---|
| `overlay-check` | 本仓或接入方 Overlay job（validate + select + run） |
| `pr-title` | PR 标题 Conventional Commits + `product/actor` 锁 |
| `sop-lock` | 仓内 SOP（workflow / 内核 / skill Lock / required_checks） |
| `Forge Ruleset` | 装了或改了保护分支 / required checks / CODEOWNERS |
| `none` | 没动门 |

不要为未知分支另开 workflow 文件。见下节。这不是分工命名。`pr-title` 只跑 `pull_request`，不要挂进 `overlay-check`（push 没有 PR 标题，不能把 overlay-check 染红）。

### 怎么验

可复制的命令，以及会入选的 **armed** suite id。本工作本常用：

```text
python3 -m forge check --root . --title "feat(overlay/dev): add cover triad and invariants"
python3 -m overlay validate --root .
python3 -m overlay cover --root .
python3 -m overlay select --branch main --root .
python3 -m overlay run --branch main --root . --workdir . --write-receipt receipts-run/
python3 -m forge apply --path forge.yaml --dry-run
python3 -m forge sop-lock --root .
python3 -m forge submit --repo OWNER/NAME --title "feat(forge/dev): add submit middleware" --dry-run
python3 -m forge pr-title --title "feat(overlay/dev): add cover triad and invariants"
```

写清：哪些 suite 应 selected、哪些应 dropped（`draft` / `blocked`）。标题：假标题单测在 `tests/forge/test_title.py`；真 PR 靠 Actions `pr-title`。

### 不做什么

至少点名：不改 LearningGuidePortal Verify；不 attach / 跑 / 门禁 Proctor；不编辑 Deepseek3；push 上不 `generate`；不 live `forge apply`；不 live-submit 本工作本进 CI；不自合；不打生产；不 vendor 工具进产品仓；不自建门户。不要用 husky/npm 当本工作本的强制 commit 门。

### 分工

**人**：谁审、谁可合。对照 [`rbac.md`](rbac.md)。不是再抄一遍标题 `actor`。

人 + Ruleset；管理端装门并合；开发端可合**别人**的已绿已批准 PR，不合自己让 agent 开的 PR；agent 不自 Approve、不自 merge。CodeRabbit 只建议。`pr-title` 红则不合。

---

## 未知分支

不要为每个 feature 分支新建 workflow。CI 仍走**同一条** `overlay-check`。某分支跑哪些 `kind` 写在接入方 `overlay.yaml` 的 `branches:`（git-chain）。表里没有的分支：`select` 空集、预演绿。本工作本把 `overlay-check` 的 `branch` 钉成 `main`，所以 `cursor/` 分支仍跑 armed 工具测试。标题检查是另一条 job，只在 PR 上跑。

这与 PR 名分工无关：不要把 `cursor/…-6842` 改成角色前缀，也不要为角色改 workflow 名或 skill 名。
