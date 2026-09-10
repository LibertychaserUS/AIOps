# 发布（两条产品 tag，不是生产 CD）

对话锁「只做 CI，不做 CD」说的是：**不打接入方生产域名，不部署 `ilovelearningguide.com`。**  
合入 `main` 之后的「发新版本」是打 **两条** GitHub Release：

| 产品 | tag 形状 | 例 |
|---|---|---|
| Overlay | `overlay-vX.Y.Z` | `overlay-v1.0.1` |
| Forge | `forge-vX.Y.Z` | `forge-v1.0.1` |

接入方 pin **tag 或 SHA**，不要 pin 浮动 `main`。GitHub 每个仓只有一个 Latest 徽章；两条 tag 都在，Latest 不代表另一条没发。

---

## 何时发

1. 进 `main` 的 PR 已 squash/合入（封顶）。
2. `overlay/__init__.py`、`forge/__init__.py`、`pyproject.toml` 的版本号已经是将打的 `X.Y.Z`。
3. 人点发布。不在 `push` 上自动发。

---

## 怎么发

在 **`main`** 上：

```text
# 本机（Ops token = FORGE_GITHUB_TOKEN 或 GITHUB_TOKEN，contents:write）
python3 -m forge release --repo LibertychaserUS/AIOps --version 1.0.1 --dry-run
python3 -m forge release --repo LibertychaserUS/AIOps --version 1.0.1
```

或 GitHub Actions：`release` workflow → **Run workflow** → `version=1.0.1` → `products=both`。  
`on:` 只有 `workflow_dispatch`。

`forge release`：缺 token 红（live）；已存在的 tag 红；拒绝 LearningGuidePortal；`make_latest=false`（不要用 Latest 当 pin）。永不 merge，不 generate，不 submit。

---

## 不做什么

- 不重钉已经有人 pin 的旧 tag（要更新就打 `1.0.1`，不要 force-move `1.0.0`）
- 不打生产
- 不在 overlay-check / forge-check / pr-title / sop-lock 里调用 `forge release`
