# CI 设计

两把锁，不要混成第三把。哪几个检查**跑**，和检查住在**哪个 workflow 文件**，是两件独立的事。

| 名 | 锁什么 |
|---|---|
| **通用检查 ≠ 产品门** | 哪个检查**跑**。通用永远跑；产品门必启动，再按 `forge.yaml` `ci` skip-success |
| **产品前缀分治**（English: **product-prefix partition**） | 哪个 **workflow 文件** 住哪个 job。一句锁：**同前缀可合，跨产品不合。** |

不要发明第三个名字。标题语法 `type(product/actor)` 的 `product`（`forge`\|`overlay`\|`ci`\|`docs`）就是这套前缀，不要另造第二种分治语法。

程序锁：[`sop-lock.md`](sop-lock.md)。选择器：`python -m forge ci-select`。标题：[`pr-brief.md`](pr-brief.md)。索引：[`sop.md`](sop.md)。

---

## 通用检查 ≠ 产品门

锁的是**跑不跑**。不是两个产品各搞一套对等 CI。

| 类 | 检查名 | 何时跑 |
|---|---|---|
| 通用（`ci` 前缀） | `pr-title`、`sop-lock` | 永远跑。`pr-title` 只在 `pull_request` |
| 产品门 | `forge-check`、`overlay-check` | workflow 必启动；跳过由 `python -m forge ci-select` / `forge.yaml` `ci` 写成 success，不靠 `on.paths` |

标题 `product` 选产品门：`overlay` → `overlay-check`；`forge` → `forge-check`；`ci` → 两门都跑；`docs` → 只跑通用。通用层不跳过。未声明的检查名 skip（`unknown-check-skip`），不当红。

本工作本 Ruleset 勾的**检查名**不变：`pr-title`、`sop-lock`、`forge-check`、`overlay-check`。改文件归属不改 check 名。

---

## 产品前缀分治

锁的是**文件归属**。一句：**同前缀可合，跨产品不合。**

| 前缀 | 住哪个文件 | 可合 |
|---|---|---|
| `ci`（通用检查） | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) only | `pr-title` + `sop-lock` 可同文件。不混进产品门 |
| `forge-*` | [`.github/workflows/forge-check.yml`](../.github/workflows/forge-check.yml) | 同 Forge 前缀可合。不进 Overlay / `ci.yml` |
| `overlay-*` | 工作本门：[`.github/workflows/overlay-check.yml`](../.github/workflows/overlay-check.yml)。接入方复用：[`.github/workflows/overlay.yml`](../.github/workflows/overlay.yml) | 同 Overlay 前缀可合。不进 Forge / `ci.yml` |
| 发布 | [`.github/workflows/release.yml`](../.github/workflows/release.yml) | **不是 CI**。人点 `workflow_dispatch` 打产品 tag |

接入方 pin reusable `overlay.yml`（**tag 或 SHA**，不要浮动 `main`），不要拷本工作本 `ci.yml`。残留的 `pr-title.yml` / `sop-lock.yml` 会让 `sop-lock` 红。

禁止：

- 把 `forge-*` job 写进 Overlay workflow，或反过来
- 把 `pr-title` / `sop-lock` 混进产品门文件
- 再做一个 mega mixed file 装两件产品
- 把 `release.yml` 当 CI
- 另造第二种分治语法（路径前缀、角色前缀、第二套标题）

---

## 本工作本文件

```text
.github/workflows/
  ci.yml              # 通用：pr-title + sop-lock（检查名不变）
  forge-check.yml     # Forge 产品门：unit + apply --dry-run；ci-select 可 skip
  overlay-check.yml   # Overlay 产品门 + Ops DAG
  overlay.yml         # reusable；接入方 pin
  release.yml         # 人点发布两条产品 tag；不是 CI
```

不要恢复 `pr-title.yml` / `sop-lock.yml`。不要把两件产品塞进同一个 workflow。

---

## 本地

```text
python3 -m forge ci-select --check overlay-check --title "feat(overlay/dev): …"
python3 -m forge sop-lock --root .
```

`sop-lock` 锁：`ci.yml` 有通用两 job 且无 `ci-select` skip；产品门文件各自 `ci-select`；残留拆文件红。不绿不能合。
