# 架构（过程稿）

**实现对照**在 [`design.md`](design.md)。Inbox：[`inbox.md`](inbox.md)。测试规格：[`test-spec.md`](test-spec.md)。本文是演进过程稿，不是现状页。

**现状**只看 [`STATE.md`](STATE.md)。对话整理已移到 [`history/2026-09-10-对话整理.md`](history/2026-09-10-对话整理.md)。

本仓是工具工作本。不代替空的同名仓。不改产品仓的构建门。不做 CD。不打生产域名。

---

## 1. 结论

两件可复用产品，叠在 GitHub 上，不要揉成一只万能云 agent，也不要做成门户。怎么接到别的仓：[`products.md`](products.md)。

1. **Forge** — 多人（和 agent）在 GitHub 上的协作：只开 PR，按分支装门，`promote` 开保护分支之间的 PR，不合入
2. **Overlay** — 可审用例 + CI（跑 `active`，丢掉 `blocked`）；不替代接入方构建门

```text
第 2 层  谁能推、谁开 PR、谁审 diff
         GitHub Rulesets + CODEOWNERS + 人 merge
                    │
                    ▼
第 1 层  inbox → 人审 active|blocked → select / run
         CPython CLI + YAML 契约 + 程序回执
```

Git 是共同账本。没有数据库、没有自建工作台。

---

## 2. 在地图上的位置

产品仓已经能构建门禁。缺的两截：需求对不齐（Overlay），多人/agent 写同一仓会踩踏（Forge）。

历史对照「没审过不跑、没证据不过」只复用语义：`blocked` 丢掉；回执由程序写。不 attach 实习监考进程，不让模型写回执。人签走 GitHub 批准 + CODEOWNERS，不再写在 suite yaml。见 [ADR 0002](adr/0002-remove-armed.md)。

Forge 规范（程序执行）：

1. 人与 agent 只能开 PR，不能直推受保护分支。
2. Agent 不能 merge、不能给自己 Approve。
3. Agent 不能在 agent 分支上把套件改成 `blocked`。
4. 不做 CD。
5. 产品构建门仍是构建门；Overlay 是第二道，不改构建 YAML。

---

## 3. 目标与非目标

做：人能读能改的用例页；两种状态 `active` / `blocked`；功能集 + 回归集；token 只在点生成时花；失败只挡 `active` 红。

不做：改接入方构建 workflow；替代构建门；打生产；自建门户；云 agent 直推保护分支。

---

## 4. 两条流水线

**生成（人点，花钱）**：inbox → `cases.md` + `suite.yaml`；经 PR 合入。未就绪人手标 `blocked` 并写带链接的 reason。

**选择 + 执行（push，不花钱）**：读 `overlay.yaml` → 只留 `active` 且 kind ∈ 该分支 → 跑 `product_command`。未知分支回落 `branches.default` 再到 `main`。

后一刀在**调用方 checkout**跑命令，不从本工作本 clone 外国产品仓。`setup_command` 先装产品工具链。

---

## 5. 技术栈

标准 CPython 3.12+。契约 YAML + JSON Schema。管仓用 GitHub Rulesets。LLM 仅 generate。CLI 见 [`cli.md`](cli.md)。
