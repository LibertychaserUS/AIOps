# Overlay 契约

权威说明 Overlay v2 套件契约、`select` / `run` / `migrate` 语义。英文入口见仓库根 `README.md`。技能：[`../skills/use-overlay/SKILL.md`](../skills/use-overlay/SKILL.md)、[`../skills/design-cases/SKILL.md`](../skills/design-cases/SKILL.md)。CI 用法：[`overlay-ci.md`](overlay-ci.md)。

本文是通用契约，不是某一家产品仓的编号表。产品示例放在 `examples/`。

## 状态机

`suites/<id>/suite.yaml` 的 `status` 只允许：

| 值 | 含义 | `select` |
|---|---|---|
| `active`（缺省） | 本切片声称可测，CI 可跑 `product_command` | 入选（还要过 branch / kind） |
| `blocked` | 已登记为未就绪，不得把门禁染红 | 丢掉，并打印 `blocked_reason` |

字段缺省 = `active`。旧值 `draft` / `armed` 在 v2 已移除：`validate` 红，提示运行：

```text
python -m overlay migrate --root .
```

已删除的字段：`reviewed_by`、`reviewed_at`、`armed_reason`。出现即红，同样给出迁移命令。

`blocked` 必须有非空 `blocked_reason`，且其中含：

- 链接 `http(s)://…`，或
- 登记编号（形如 `OF-12`、`#123`），或
- 相对 Markdown 路径（如 `CHANGELOG.md#overlay-200`、`docs/adr/0002-remove-armed.md`）

`overlay.yaml` 的 `never_red_statuses` 仍保留，但只接受 `blocked`。`select` 丢掉 blocked 时打印 reason。

## 文件清单

接入方产品仓只提交：

```text
overlay.yaml
inbox/<id>.md
suites/<id>/suite.yaml
suites/<id>/cases.md
suites/<id>/trace.yaml     # 可选
invariants.yaml            # 可选
.github/workflows/overlay-check.yml   # reusable 调用或等价 inline
```

不要把工具仓的 `overlay/`、`forge/`、`schema/` vendor 进产品仓。

`suite.yaml` 必须声明 `schema: overlay-suite/v2`。`overlay.yaml` 仍是 `schema: overlay-config/v1`（配置未破坏）。旧 `overlay-suite/v1` → 迁移提示。

## 叶子三技法

`overlay validate` 把每个 `##` 标题的第一个无空白 token 当作 `function_id`。`active` 叶子必须有三个 `###` 技法标题：

```markdown
## AUTH-01
### Functional
### Negative
### Edge
```

- 标题必须是 **`### Functional` / `### Negative` / `### Edge`**（大小写不敏感）。不要写 `### Depth`。
- 不要写 `## Specified`（或任何散文 `##`）。它会变成 `function_id`。
- `function_id` 在整个 overlay root **全局唯一**。
- `invariants.yaml` 的 `function_ids` 必须对上已有 `##` 标题。invariant id 必须作为 token 出现在某篇 `cases.md`。
- `blocked` 可以薄：缺技法时 `cover` 只提示，不把门禁染红。

## `select`

```text
python -m overlay select --branch <name> --root .
```

- `--branch X` 只查 `overlay.yaml` 的 `branches.X` 策略；套件状态读当前 checkout。
- `--branch` 缺省：环境变量 `GITHUB_BASE_REF` → `GITHUB_REF_NAME` → `main`。
- 未知分支不是全部丢掉：回落到 `branches.default`（若配置）再到 `main`，并打印一行说明。
- 只入选 `status: active` 且 `kind` 在该分支 `run:` 列表里的套件。`blocked` 丢掉且不红。
- `kinds: later`（以及 `subject: agent`）丢掉。
- 失败的 `product_command` 才会把 `run` 染红（退出 5）。命中 `forbid_hosts` → 退出 2，命令不启动。

## `run`

保持 `bash -c`。`--timeout` 为每条命令秒数（默认 600）。回执里 `ran` 事件记录：

- `exit`（进程退出码；超时为 124）
- `duration_s`
- `command_sha256`（命令文本的 sha256）
- `command`（命令原文；不要把命令以外的密钥写进回执）

`--write-receipt` 必填。回执只能由 `select` / `run` 写，`wrote_by` 不得是 model。

## `forbid_hosts`

`overlay.yaml` 的 `forbid_hosts` **只是字符串匹配**，用来防手滑把生产域名写进 `product_command`。它不是安全边界，也不是网络隔离。

## 迁移

```text
python -m overlay migrate --root . [--dry-run]
```

逐行改写，不 `yaml.dump` 重排：

- `draft` / `armed` → `active`
- `blocked` 保留
- 删除 `reviewed_by` / `reviewed_at` / `armed_reason`
- 写入 `schema: overlay-suite/v2`
- `blocked` 缺 `blocked_reason` 时不改该文件，打印待办
- `overlay.yaml` 的 `never_red_statuses` 若含 `draft` 一并删掉

`--dry-run` 只打印将改写的路径。
