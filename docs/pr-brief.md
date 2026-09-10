# PR 解说规格

GitHub PR 是解说面。DevOps 和其他 agent 读**标题 + 正文**就知道做了什么，不靠翻 diff。不是门户，不另做解说站。

「分工」写在 **GitHub PR 名（标题）前缀**。只这一处。不是分支名，不是 workflow 的 `name:`，不是 `skills/<name>/`。不要另造 `管理/`、`开发/`、`agent/` 分支前缀。Forge 已有的 `agent_branch_prefixes`（默认 `cursor/`、`copilot/`，如 `cursor/overlay-architecture-6842`）管谁的分支能推，不是本规格；这类分支名不要改。

标题前缀只标明这单活戴哪顶帽子、碰哪件产品。谁审、谁合仍是 GitHub 上的人 + Ruleset，见 [`rbac.md`](rbac.md)。不要把标题前缀当成权限。

开 PR 用 [`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)。开发写规格。管理拒收：标题无此前缀，或正文缺下面任一稳定标题。开发端：[`../skills/dev-pr/SKILL.md`](../skills/dev-pr/SKILL.md)。管理端：[`../skills/manage-repo/SKILL.md`](../skills/manage-repo/SKILL.md)。

---

## PR 名（标题）前缀

必填。两个方括号，然后一个空格，然后一句祈使动词：

```text
[<role>][<product>] <imperative>
```

| 槽 | 取值 | 写什么 |
|---|---|---|
| `role` | `管理` \| `开发` \| `agent` | 这单戴哪顶帽子 |
| `product` | `Forge` \| `Overlay` \| `CI` \| `docs` | 主产品。混改写在「做了什么」，不要叠第二个产品括号 |
| 一行 | 祈使、一事 | 不要散文标题 |

例：

- `[开发][Overlay] add cover triad and invariants`
- `[开发][Overlay] add overlay run to overlay-check`
- `[管理][docs] add PR brief spec`

合法：分支仍叫 `cursor/fix-armed-select`，标题写成 `[开发][Overlay] fix armed select`。  
非法：把分支改成 `开发/overlay-fix` 来表示角色。非法：把 `overlay-check` 或 `dev-pr` 改名来表示角色。

混改：标题只标主产品。其余列在「做了什么」。不要写成 `[开发][Overlay+docs+CI]`。

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
| `Forge Ruleset` | 装了或改了保护分支 / required checks / CODEOWNERS |
| `none` | 没动门 |

不要为未知分支另开 workflow 文件。见下节。这不是分工命名。

### 怎么验

可复制的命令，以及会入选的 **armed** suite id。本工作本常用：

```text
python3 -m overlay validate --root .
python3 -m overlay cover --root .
python3 -m overlay select --branch main --root .
python3 -m overlay run --branch main --root . --workdir . --write-receipt receipts-run/
python3 -m forge apply --path forge.yaml --dry-run
```

写清：哪些 suite 应 selected、哪些应 dropped（`draft` / `blocked`）。

### 不做什么

至少点名：不改 LearningGuidePortal Verify；不 attach / 跑 / 门禁 Proctor；不编辑 Deepseek3；push 上不 `generate`；不 live `forge apply`；不打生产；不 vendor 工具进产品仓；不自建门户。

### 分工

**人**：谁审、谁可合。对照 [`rbac.md`](rbac.md)。不是再抄一遍标题前缀。

人 + Ruleset；管理端装门并合；开发端可合**别人**的已绿已批准 PR，不合自己让 agent 开的 PR；agent 不自 Approve、不自 merge。CodeRabbit 只建议。

---

## 未知分支

不要为每个 feature 分支新建 workflow。CI 仍走**同一条** `overlay-check`。某分支跑哪些 `kind` 写在接入方 `overlay.yaml` 的 `branches:`（git-chain）。表里没有的分支：`select` 空集、预演绿。本工作本把 `overlay-check` 的 `branch` 钉成 `main`，所以 `cursor/` 分支仍跑 armed 工具测试。

这与 PR 名分工无关：不要把 `cursor/…-6842` 改成角色前缀，也不要为角色改 workflow 名或 skill 名。
