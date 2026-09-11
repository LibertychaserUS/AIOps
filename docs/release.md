# 发布（两条产品 tag，不是生产 CD）

对话锁「只做 CI，不做 CD」说的是：**不打接入方生产域名，不部署 `ilovelearningguide.com`。**  
合入 `main` 之后的「发新版本」是打 **两条** GitHub Release：

| 产品 | tag 形状 | 例 |
|---|---|---|
| Overlay | `overlay-vX.Y.Z` | `overlay-v1.0.1` |
| Forge | `forge-vX.Y.Z` | `forge-v1.0.1` |

接入方 pin **已经存在的 tag 或 SHA**，不要 pin 浮动 `main`。当前官方针是 git tag [`overlay-v1.0.1`](https://github.com/LibertychaserUS/AIOps/tree/overlay-v1.0.1) / [`forge-v1.0.1`](https://github.com/LibertychaserUS/AIOps/tree/forge-v1.0.1)（`b4afc10ae0be4725e5109030f14a05bb2291fe4a`）。`1.0.1` 的 GitHub Release 对象还没建，不要链 `/releases/tag/overlay-v1.0.1`。旧针 [`overlay-v1.0.0`](https://github.com/LibertychaserUS/AIOps/releases/tag/overlay-v1.0.0) / [`forge-v1.0.0`](https://github.com/LibertychaserUS/AIOps/releases/tag/forge-v1.0.0) 不要 force-move。不要让 README 指向还不存在的下一版 tag。GitHub 每个仓只有一个 Latest 徽章；两条 `1.0.1` tag 都在，Latest 仍挂 `1.0.0`。

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
# 人确认新 tag 还不存在之后再发。不要 force-move 已有针。
python3 -m forge release --repo LibertychaserUS/AIOps --version X.Y.Z --dry-run
python3 -m forge release --repo LibertychaserUS/AIOps --version X.Y.Z
```

或 GitHub Actions：`release` workflow → **Run workflow** → `version=X.Y.Z` → `products=both`。  
`on:` 只有 `workflow_dispatch`。

`forge release`：缺 token 红（live）；已存在的 tag 红；拒绝 LearningGuidePortal；`make_latest=false`（不要用 Latest 当 pin）。永不 merge，不 generate，不 submit。

---

## 不做什么

- 不重钉已经有人 pin 的旧 tag（要更新就打 `1.0.1`，不要 force-move `1.0.0`）
- 不打生产
- 不在 overlay-check / forge-check / pr-title / sop-lock 里调用 `forge release`

---

## 1.0.1 honesty (do not retag)

`overlay-v1.0.1` / `forge-v1.0.1` exist as annotated git tags at `b4afc10ae0be4725e5109030f14a05bb2291fe4a`. SOP is **Human / Ops** (`人点发布` / `python -m forge release` / Actions `release` `workflow_dispatch`). The tags were pushed; GitHub Release objects may still be missing (`gh release view overlay-v1.0.1` 404; `gh release create` is 403 for `cursor[bot]`). Do not delete or force-move those tags. Ops should create the Release pages for the existing tags, or own the next semver. Pin the git tag (`git checkout overlay-v1.0.1` / `/tree/overlay-v1.0.1`), not a missing `/releases/tag/` page.
