# Inbox 设计

Overlay 的输入面。实现对照以本文 + [`design.md`](design.md) §4 为准。Front matter JSON Schema：[`schema/inbox.schema.json`](../schema/inbox.schema.json)。

Inbox **不是**用例，**不是**门禁，**不是**产品仓里的那份大 PRD。它是：人（产品）用一篇短 Markdown 说「请就这个范围出可审用例」。`generate` 只读这里。`select` / `run` 不读这里。

---

## 1. 原则

| 原则 | 含义 |
|---|---|
| 一篇一刀 | 一个 `inbox/<id>.md` 对应一次 `generate`，产出一个 `suites/<id>/`。`id` 相同。 |
| 人写需求，模型写草稿 | Inbox 由人经 PR 提交（Forge：不直推保护分支）。`generate` 不改 inbox。 |
| 短、可进 git | 正文是摘录或 user case，禁止把 700KB+ docx/pdf 拷进仓。 |
| 来源可核对 | 若声明 `source`，必须 pin 到 commit/tag，禁止 `main`/`HEAD`。 |
| 不管跑不跑 | Inbox **没有** `status`。解禁只发生在 `suite.yaml`。 |
| 与业务无关 | 字段不出现某产品的路由或域名。那些只写在 fixture 正文里。 |

不做：inbox 数据库、上传门户、自动从 Figma 拉帧、第一刀去产品仓解压 docx。

---

## 2. 文件

```text
inbox/
  <id>.md          # 唯一允许的形状；不要子目录（第一刀）
```

- 文件名 = `id` + `.md`。只扫这一层。`_` / `.` 开头的文件忽略。
- `id`：`^[a-z0-9][a-z0-9-]*$`，最长 64。
- 编码 UTF-8。无 BOM。换行 LF。
- 体积：整文件 ≤ 32 KiB；front matter 外正文 ≤ 8 000 字（校验按 Unicode 字计）。超了 `validate` 失败。
- 一篇 inbox 在仓内 `id` 唯一；必须能一对一落到 `suites/<id>/`（可以还没有 suite，表示尚未 generate）。

---

## 3. 文档形状

标准 Markdown，**必须**有且仅有一段开头 YAML front matter（`---` … `---`）。其后是正文。

```markdown
---
id: checkout-retry
kind: user-case
readiness: not-ready
source:
  repo: acme/shop
  path: docs/prd/checkout.md
  ref: abcdef1
packages:
  - src/checkout
---

## Intent
一句话：用户付费失败后能重试且不双扣。

## In scope
- 失败页上的「重试」
- 幂等键已存在时不新建支付

## Out of scope
- 新的支付渠道

## User cases
1. 网络超时后点重试，仍是同一笔。
2. 已成功的 receipt 再点重试，提示已完成。

## Notes
未就绪：真卡 / 生产 webhook。审的时候应标 blocked。
```

正文推荐这五个标题（生成器按标题切，缺了也能跑，但质量差）：

| 节 | 写什么 |
|---|---|
| Intent | 一段话，这个 inbox 要测的行为 |
| In scope | 可出用例的范围 |
| Out of scope | 明确不测 |
| User cases | 编号场景；`kind: user-case` 时本节是主体 |
| Notes | 给审的人：哪些该 blocked |

`kind: prd`：In scope 里写需求条（一行一条，生成器抽成 REQ-n）。  
`kind: figma-ref`：正文只许 `https://` 链接列表 + 一句对照说明，不许贴图二进制。

禁止在正文放密钥、真实卡号、完整学生 prompt、生产 URL（`overlay.yaml` 的 `forbid_hosts` 命中则 validate 失败）。

---

## 4. Front matter

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `id` | string | 是 | 等于文件名；见上 |
| `kind` | enum | 是 | `prd` \| `user-case` \| `figma-ref` |
| `readiness` | enum | 否 | `ready` \| `not-ready` \| `unknown`（默认 `unknown`） |
| `source` | object | 否 | 有则 `repo`+`path`+`ref` 都要 |
| `source.repo` | string | 随 source | `owner/name` |
| `source.path` | string | 随 source | 仓内相对路径，不 `..` |
| `source.ref` | string | 随 source | **拒绝** `main`/`master`/`HEAD`/`latest`。正式 generate 应 pin commit（≥7 hex）或 tag。fixture 可用 `pin-me` 直到有 SHA |
| `packages` | string[] | 否 | 生成时原样写入 `suite.yaml`；第一刀可 `[]` |
| `locale` | string | 否 | 提示词语言，默认 `en-GB`；不驱动产品 i18n |

**没有**这些字段（放了 validate 失败）：`status`、`reviewed_by`、`armed`、`blocked`、`product_command`。那是 suite 的。

### `readiness` 是提示，不是门

| 值 | 含义 | generate | 人审 |
|---|---|---|---|
| `ready` | 作者认为代码已可测 | 仍出 `draft` | 人可以标 `armed` |
| `not-ready` | 作者认为不该进门禁 | 仍出 `draft`；把提示抄进 `cases.md` 顶部 | 人应标 `blocked`（不自动） |
| `unknown` | 没表态 | 仍出 `draft` | 人决定 |

实现不得因为 `readiness: ready` 写出 `status: armed`。

---

## 5. 生命周期

```text
产品（或人）开 PR 增加/改 inbox/<id>.md
        │  Forge：不直推保护分支
        ▼
overlay validate          只查契约与体积，不调模型
        │
        │ 人点或 workflow_dispatch
        ▼
overlay generate --inbox inbox/<id>.md
        │  只读 inbox；写出 suites/<id>/（status=draft）
        │  不改 inbox
        ▼
人审 suite.yaml           inbox 保持不动，除非需求变了再改摘录
```

| 动作 | 改 inbox？ | 改 suite？ |
|---|---|---|
| 产品改需求摘录 | 是（新 PR） | 否；需要则重新 generate（`--force-draft`） |
| generate | 否 | 是，只许变成/保持 draft |
| 人审 blocked/armed | 否 | 是 |
| select / run | 否 | 否 |

`source` 指向的大 PRD 更新了：人改 `source.ref` + 必要时改正文摘录。Overlay 第一刀不自动去拉 docx。

---

## 6. 和 suite / generate 的接法

- `generate` 的 `--inbox` 必须是 `inbox/<id>.md`。输出目录默认 `suites/<id>/`。
- 写出的 `suite.yaml`：`id`、`source: inbox/<id>.md`、`packages` 从 inbox 拷；`status: draft`；`reviewed_*` 空。
- `cases.md` 开头可写一行：`<!-- inbox-readiness: not-ready -->` 给审的人看。
- 一对多：**第一刀不做**。支付、登录、My Learning = 三篇 inbox，三个 suite。不要一篇 inbox 生成三个目录。
- 多对一：禁止。两个 inbox 不得指向同一 `suites/<id>/`。

---

## 7. 校验（`overlay validate`）

对每个 `inbox/*.md`：

1. 能切开 front matter；YAML 可解析。
2. 字段表全部满足；无未知字段（`additionalProperties: false`）。
3. `id` == 文件名。
4. 体积与字数上限。
5. 正文非空（去掉空白后 ≥ 40 字，避免只有标题）。
6. `kind: figma-ref` 时正文每条链接是 `https://`。
7. `source.ref` 不在拒绝名单（`main`/`master`/`HEAD`/`latest`）。fixture 的 `pin-me` 可通过。
8. 正文不含 `forbid_hosts`（读接入方 `overlay.yaml`）。
9. 无 suite 也可以过（尚未 generate 不是错）。
10. 若已有 `suites/<id>/suite.yaml`，其 `source` 必须等于 `inbox/<id>.md`。

Inbox 校验失败 = Overlay **契约红**（退出码 2），与 `blocked` 不当红不是同一件事。

---

## 8. CLI

```text
python -m overlay inbox-new --id ID --kind user-case
    # 写出带空节的模板，不调模型

python -m overlay validate
    # 含全部 inbox

python -m overlay generate --inbox inbox/ID.md
```

`inbox-new` 给产品一个能开 PR 的空壳。不代替人写 Intent / User cases。

---

## 9. 接入方怎么用

1. 每条要对齐的需求范围 = 一篇 inbox（宁可多篇短的，不要一篇全集）。
2. 未就绪范围单独成篇，`readiness: not-ready`，审成 `blocked`。
3. 大 PRD 留在产品仓，inbox 只 pin + 摘录。
4. 走 PR 合入 inbox（装了 Forge 就自然如此）。

Learning Guide fixture：

| 文件 | kind | readiness | 审完 suite | 产品仓 `source.path` |
|---|---|---|---|---|
| `inbox/my-learning.md` | prd | ready | 可 `armed` | `My_Learning_PRD_v1.0_0814.docx` |
| `inbox/payment.md` | prd | not-ready | 必须 `blocked` | `Payment_Management_PRD_v1.0_0814.docx` |
| `inbox/login.md` | prd | not-ready | 必须 `blocked` | `Registration_Authentication_PRD_v1.0_0814.docx` |

---

## 10. 非目标（inbox 专条）

- 在 inbox 里写 Playwright / 断言代码当正文主体。
- 用 inbox 当 wiki 或会议纪要。
- 第一刀解析 docx/xlsx/Figma 节点。
- Agent 不经 PR 改保护分支上的 inbox。
- 从 inbox 直接 `armed`。
