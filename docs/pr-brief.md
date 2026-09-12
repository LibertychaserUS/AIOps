# PR 解说规格

GitHub PR 是解说面。DevOps 和其他 agent 读**标题 + 正文**就知道做了什么，不靠翻 diff。不是门户，不另做解说站。

本规格锁的是 **进保护发布枝的那颗提交**，不是功能枝上每一颗中间 commit。默认落地是 **squash**：一单 PR 压成目标枝上的一颗，标题就是那颗的 Conventional Commits header。这是提交内容的规格化，和标题语法同一层。

「分工」写在 **GitHub PR 标题** 的 Conventional Commits scope（`product/actor` 的 `actor`）。只这一处。不是分支名，不是 workflow 的 `name:`，不是 `skills/<name>/`。不要另造 `管理/`、`开发/`、`agent/` 分支前缀。Forge 已有的 `agent_branch_prefixes`（默认 `cursor/`、`copilot/`，如 `cursor/overlay-architecture-6842`）管谁的分支能推，不是本规格；这类分支名不要改。

标题 `actor` 只标明这单活戴哪顶帽子；`product` 标明碰哪件产品。谁审、谁合仍是 GitHub 上的人 + Ruleset，见 [`rbac.md`](rbac.md)。不要把标题当成权限。

开 PR 用 [`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)。开发写规格。管理拒收：`pr-title` 红，或正文缺下面任一稳定标题。开发端：[`../skills/dev-pr/SKILL.md`](../skills/dev-pr/SKILL.md)。管理端：[`../skills/manage-repo/SKILL.md`](../skills/manage-repo/SKILL.md)。

本地锁（程序，无模型、不写 GitHub）：

```text
python -m forge check --root . --title "feat(overlay/dev): add cover triad and invariants"
python -m forge pr-title --title "feat(overlay/dev): add cover triad and invariants"
```

退出 `0` 绿、`2` 红。CI job **`pr-title`** 只挂 `pull_request`（读 `PR_TITLE` / `PR_BODY`）。`forge check` 在 `push` 上另锁 HEAD 提交第一行，见下节。工作本实际勾哪些 checks 见 [`STATE.md`](STATE.md)。代推前 `python -m forge check` 红则不能提交；缺 `FORGE_SUBMIT_TOKEN` 也不能提交（含 `--dry-run`）。不要 live `forge apply`。不要用 husky/npm 挡 `git commit`。子命令见 [`cli.md`](cli.md)。

## 事件与标题来源

旧夹具只锁「好 `--title` / `--title ""` / 缺 actor」。没锁到 `push` 对 `pull_request.title` 的空串、也没锁 `forge check` 把 pr-title 嵌进 push。把空白环境变量当成省略是绕过，不是覆盖。

| 状态 | 来源 | 结果 |
|---|---|---|
| `--title` / `--body` 已给（含 `""`） | 参数 | lint；空参数仍红 |
| 非空 `PR_TITLE` / `PR_BODY` | 环境 | lint |
| `pull_request` + 空白或未设 | 空规格 | 标题红；有本文件时正文缺六个 `##` 也红 |
| `push` 或 Actions 空串（环境已设、不是 `pull_request`） | HEAD 提交第一行 | lint 该 subject |
| 本地、无事件、环境未设 | 省略 | `forge check` 该步 skip |

`ci-select` 在 push 且 `PR_TITLE` 为空时，用提交标题的产品面，不把空串当成「无标题 → 只看路径」。程序锁：`FN-forge-pr-title`，`INV-pr-spec-event-states`。详表见 [`forge-config.md`](forge-config.md)。

本仓 PR #3 的 GitHub 标题已由人在 UI 定为（不要再改，除非完全不准）：

```text
feat(overlay/agent): adopt Overlay CI and Conventional Commit PR titles
```

不要改成 `feat(ci/agent): split overlay and forge CI workflows`。那是「两个产品各搞一套对等 CI」的旧说法。

标题 `product` 同时驱动 `python -m forge ci-select`（`forge.yaml` `ci.select.title`）：`overlay` → `overlay-check`；`forge` → `forge-check`；`ci` → 两个都跑；`docs` → 只跑通用。**通用检查 ≠ 产品门。** 不要另造第二种标题语法。

---

## 进保护分支的提交（squash 封顶）

核心原理（提交内容规格化）：

**要进保护分支的 PR，必须是整段工作的封顶。合完立刻以目标枝上那颗新 SHA 为底再开下一枝。不要从即将被压掉的旧头再叠。**

| 锁 | 意思 |
|---|---|
| 封顶 | 这一单 PR 是整段工作。squash 之后 `main` 上只多一颗，标题就是那颗 header |
| 压完换底 | 下一枝从 `main` 的新 SHA 开。旧功能枝头不再当 base |
| 不叠旧头 | 禁止把未合 / 即将 squash 的 `cursor/…` 当下一单的 base。血缘在 squash 后断开 |

`python -m forge submit` 的 base 是 `forge.yaml` `protect[0]`（常见为 `dev`），`--base` 必须在 `protect`。不开到另一条功能枝。GitHub 合入默认 squash。merge commit / rebase 也能用，但不改变这条：封顶再压，压完换底。

封顶之后，这一单装什么按**层配对**，不是「文档 + 代码 + workflow 每次都齐」。碰哪一层带哪一组；没碰的层不要塞。workflow 是独立的 Ops 包（产品仓常在 `deny_paths`），不要塞进功能切片。见表与五种包：[`forge-config.md`](forge-config.md)「内容包」、[ADR 0007](adr/0007-content-package-layers.md)。

非法：#3 squash 之后还拿旧架构枝开 #4 / #5。合法：#5 squash 进 `main`，下一单从新的 `main` 头开。

没有单独的 ISO / RFC 叫「封顶换底」。行业权威锁的是**进主干的那颗提交**，拓扑后果写在平台文档里：

| 权威 | 锁什么 | 和本仓 |
|---|---|---|
| [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) FAQ | 规格管 **commit message**。允许 squash：维护者在合入时整理信息，「automatically squash commits from a pull request」 | 标题语法锁的是 squash 进 `main` 的那颗，不是功能枝每一颗 WIP |
| [GitHub · About pull request merges](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges) | Squash：**one logical change**。短命枝。合完还在同一 head 上继续开 PR，会把已经压进 base 的提交再带进来 | 「封顶」= one logical change；「换底」= 官方对 long-running branch 的警告 |
| [GitHub · squash 默认用 PR 标题](https://github.blog/changelog/2022-05-11-default-to-pr-titles-for-squash-merge-commit-messages/) + 仓设置 `squash_merge_commit_title=PR_TITLE` | squash 提交的 subject 默认是 PR 标题 | 所以 `pr-title` 锁标题 = 锁 `main` 上的 commit header |
| [amannn/action-semantic-pull-request](https://github.com/amannn/action-semantic-pull-request) | 为 squash + [semantic-release](https://github.com/semantic-release/semantic-release) 而写；建议仓设置 Default to PR title | 本仓用 CPython 做同一件事，不引入 Node |
| [GitLab · Squash and merge](https://docs.gitlab.com/ee/user/project/merge_requests/squash_and_merge/) | 一单 MR 合成一颗有意义的提交；多功能分开压，主干只留逻辑单元 | 同一句：一单 = 一颗 |
| [Graphite · restack / merge stack](https://graphite.com/docs/restack-branches) | 叠枝产品。底 squash 之后必须 `gt sync` / restack 到**新的 trunk SHA**。从 GitHub 直接合、不 restack，上枝会坐在已消失的旧父 SHA 上 | 这就是 #3 之后 #4/#5 的事故。本仓不接 Graphite；用「不叠旧头 + 换底」代替自动 restack |

Linux `gitworkflows(7)` 是 merge-commit / 集成枝模型，和 squash-to-trunk 不是同一套，不拿来当本仓合入法。

合入默认仍 squash。要叠，必须像 Graphite 那样在底合入后 restack 到新 `main`；本仓第一刀不做 restack 机器人，所以 `submit` 只开到 `protect`。

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
| `product` | `forge` \| `overlay` \| `ci` \| `docs` | 主产品，也是产品门选择器。`overlay` / `forge` 各跑对应门；`ci` 两门都跑；`docs` 只跑通用。混改写在「做了什么」，不要叠第二个产品 |
| `actor` | `dev` \| `admin` \| `agent` | 这单戴哪顶帽子。映射：开发端=`dev`，管理端=`admin`，agent=`agent` |
| `!` | 可选 | Conventional Commits breaking，紧贴 `)` 与 `:` |
| `subject` | 非空、不以空白开头 | 祈使、一事。不要散文标题 |

例：

- `feat(overlay/dev): add cover triad and invariants`
- `feat(overlay/dev): add overlay run to overlay-check`
- `docs(docs/admin): add PR brief spec`

合法：分支仍叫 agent 前缀 + 功能名，标题写成 `fix(overlay/dev): fix select drop`。  
非法：把分支改成 `开发/overlay-fix` 来表示角色。非法：把 `overlay-check` 或 `dev-pr` 改名来表示角色。非法：`[开发][Overlay] fix select`。

混改：标题只标主产品。其余列在「做了什么」。不要写成 `feat(overlay+docs/dev):`。

可选本地包装（不默认安装 git hook）：`forge/hooks/pr-title "feat(overlay/dev): …"`；提交前整门：`forge/hooks/pre-submit --title "…"`。代推锁是 `python -m forge check` 绿，**并且** 持有 `FORGE_SUBMIT_TOKEN`。`gh auth` / `GH_TOKEN` / extraheader 都不够。合并锁是 GitHub 上的 required checks，不是本机 hook。

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

对照哪条契约或 git-chain：[`design.md`](design.md)、[`adr/`](adr/)、Overlay `function_id` / 状态机、Forge Ruleset。一句话到一小段。

### 动了哪些门

只许这些值（可并列）：

| 值 | 含义 |
|---|---|
| `overlay-check` | 本仓或接入方 Overlay job（validate + select + run Overlay `active`） |
| `pr-title` | PR 标题 Conventional Commits + `product/actor` 锁 |
| `forge-check` | 本仓 Forge **产品门**（unit + apply --dry-run；`forge.yaml` `ci` 选跑或跳过） |
| `sop-lock` | 仓内 SOP（workflow / 内核 / skill Lock / required_checks） |
| `Forge Ruleset` | 装了或改了保护分支 / required checks / CODEOWNERS |
| `none` | 没动门 |

不要为未知分支另开 workflow 文件。见下节。这不是分工命名。CI job `pr-title` 只挂 `pull_request`。不要把 job `pr-title` 挂进 `overlay-check` 的 push 路径；push 上的标题锁由 `forge check` / `python -m forge pr-title` 对 HEAD 提交执行，不是把 overlay-check 当标题门。

### 怎么验

可复制的命令见 [`cli.md`](cli.md)，以及会入选的 **active** suite id。本工作本常用：

```text
python3 -m forge check --root . --title "feat(overlay/dev): add cover triad and invariants"
python3 -m forge sop-lock --root .
```

写清：哪些 suite 应 selected、哪些应 dropped（`blocked`）。标题：假标题单测在 `tests/forge/test_title.py`；真 PR 靠 Actions `pr-title`。

### 不做什么

至少点名：不改接入方构建门；不 attach 监考进程；push 上不 `generate`；不 live `forge apply`；不 live-submit 本工作本进 CI；不自合；不打生产；不 vendor 工具进产品仓；不自建门户。不要用 husky/npm 当本工作本的强制 commit 门。

### 分工

**人**：谁审、谁可合。对照 [`rbac.md`](rbac.md)。不是再抄一遍标题 `actor`。

人 + Ruleset；管理端装门并合；开发端可合**别人**的已绿已批准 PR，不合自己让 agent 开的 PR；agent 不自 Approve、不自 merge。CodeRabbit 只建议。`pr-title` 红则不合。

---

## 未知分支

不要为每个 feature 分支新建 Overlay workflow。Overlay CI 仍走**同一条** `overlay-check` 家族。某分支跑哪些 `kind` 写在接入方 `overlay.yaml` 的 `branches:`（git-chain）。未知分支回落 `branches.default` 再到 `main`。产品门按 `forge.yaml` `branches:` 选跑或跳过成功。通用 job `pr-title` 只在 `pull_request` 上跑且不 skip；`forge check` 在 `push` 上锁的是提交 subject，同样不因空 `PR_TITLE` 卸锁。

这与 PR 名分工无关：不要把 `cursor/…-6842` 改成角色前缀，也不要为角色改 workflow 名或 skill 名。
