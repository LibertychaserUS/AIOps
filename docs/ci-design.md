# CI 设计

两把锁，不要混成第三把。哪几个检查**跑**，和检查住在**哪个 workflow 文件**，是两件独立的事。

| 名 | 锁什么 |
|---|---|
| **通用检查 ≠ 产品门** | 哪个检查**跑**。通用永远跑；产品门必启动，再按 `forge.yaml` 写成 success 或真跑 |
| **产品前缀分治** | 哪个 **workflow 文件** 住哪个 job。一句：**同前缀可合，跨产品不合。** |

不要发明第三个名字。标题里的产品前缀（`forge` / `overlay` / `ci` / `docs`）就是这套前缀。

程序锁：[`sop-lock.md`](sop-lock.md)。选择器与子命令：[`cli.md`](cli.md)。标题：[`pr-brief.md`](pr-brief.md)。索引：[`sop.md`](sop.md)。现状（job 名、required checks）：[`STATE.md`](STATE.md)。

---

## 通用检查 ≠ 产品门

| 类 | 检查名 | 何时跑 |
|---|---|---|
| 通用 | `pr-title`、`sop-lock` | 永远跑。`pr-title` 只在 `pull_request` |
| 工作本单测 | `unittest` | **永远跑**，不走 ci-select。命令：`python3 -m unittest discover -s tests -t . -q` |
| 产品门 | `forge-check`、`overlay-check` | workflow 必启动；跳过由 `ci-select` 写成 success，不靠 `on.paths` |

标题 `product` 选产品门：`overlay` → `overlay-check`；`forge` → `forge-check`；`ci` → 两门都跑；`docs` → 只跑通用。通用层与 `unittest` 不跳过。未声明的检查名 skip，不当红。

接入方不要拷本工作本 `ci.yml`。Overlay 接入方 pin reusable `overlay.yml`。`required_checks` 填真实 **CI job 名**。按分支规则见合入后的 `forge-config.md` 与 [ADR 0004](adr/0004-per-branch-rulesets.md)。

`sop-lock` 放行 `ci.yml` 里的 `unittest` job（不得把旁路 unittest 写进 Overlay push workflow 来绕过 select）。

`forge-check` 另跑 `forge status --check-state`（校验 STATE 新鲜）。

---

## 产品前缀分治

| 前缀 | 住哪个文件 |
|---|---|
| `ci`（通用 + 工作本 `unittest`） | `.github/workflows/ci.yml` |
| `forge-*` | `forge-check.yml` |
| `overlay-*` | 工作本门 `overlay-check.yml`；接入方复用 `overlay.yml` |
| 发布 | `release.yml`（**不是 CI**。人点 `workflow_dispatch`） |

禁止：跨产品合文件；把 `pr-title` / `sop-lock` 混进产品门；把 `release.yml` 当 CI；用 `on.paths` 让检查根本不启动。残留的 `pr-title.yml` / `sop-lock.yml` 会让 `sop-lock` 红。

接入方 pin reusable `overlay.yml`（tag 或 SHA）。`setup_command` 在 run job 装产品工具链。`--branch` 缺省 `github.base_ref` / `github.ref_name`。Node / Python / Go / Java 的 `runtime_setup` 示例见合入后的 `overlay-ci.md`。

---

## 本工作本文件

```text
.github/workflows/
  ci.yml              # 通用：pr-title + sop-lock；另 job unittest 永远跑
  forge-check.yml     # Forge 产品门
  overlay-check.yml   # Overlay 产品门 + Ops DAG
  overlay.yml         # reusable；接入方 pin
  release.yml         # 人点发布两条产品 tag
```

---

## 本地

见 [`cli.md`](cli.md)。`sop-lock` 不绿不能合。
