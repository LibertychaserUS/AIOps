# 发布（两条产品 tag，不是生产 CD）

「只做 CI，不做 CD」：**不打接入方生产域名，不部署。**  
合入保护分支之后的「发新版本」是打 **两条** GitHub Release：

| 产品 | tag 形状 | 例 |
|---|---|---|
| Overlay | `overlay-vX.Y.Z` | `overlay-v2.0.0` |
| Forge | `forge-vX.Y.Z` | `forge-v1.1.0` |

接入方 pin **已经存在的 tag 或 SHA**，不要 pin 浮动 `main`。不要 force-move 已有针。GitHub 每个仓只有一个 Latest 徽章；两条产品 tag 都要 pin 具体 tag，不要拿 Latest 当针。

**现状 pin** 只看 [`STATE.md`](STATE.md)。CHANGELOG：[`../CHANGELOG.md`](../CHANGELOG.md)。CLI：[`cli.md`](cli.md)。

---

## 何时发

1. 进保护发布枝的 PR 已合入（**封顶**）。
2. `overlay/__init__.py`、`forge/__init__.py`、`pyproject.toml` 的版本号已经是将打的 `X.Y.Z`。
3. `CHANGELOG.md` 已有 `## [overlay-X.Y.Z]` 和/或 `## [forge-X.Y.Z]` 段（按 `--products`）。缺段则 `release` 红。
4. 人点发布。不在 `push` 上自动发。

`--products` 分开时版本可不同：`--version` 对单产品；`both` 要求两产品 `__version__` 相同（否则分两次跑）。Release 正文 = 该 CHANGELOG 段 + 固定尾注。已有 tag 指向别的提交则红。

---

## 怎么发

在发布枝上：

```text
python3 -m forge release --repo OWNER/NAME --version X.Y.Z --dry-run
python3 -m forge release --repo OWNER/NAME --version X.Y.Z
```

或 GitHub Actions：`release` workflow → **Run workflow** → `version=X.Y.Z` → `products=both`。  
`on:` 只有 `workflow_dispatch`。

缺 token 红（live）；已有 Release 红；tag 已存在但指向别的提交红；tag 已存在且就在目标 SHA 上则只补 Release。`make_latest=false`。永不 merge，不 generate，不 submit。禁仓见 `forbidden_live_repos`。

---

## 不做什么

- 不重钉已经有人 pin 的旧 tag（要更新就打新 semver）
- 不打生产
- 不在 overlay-check / forge-check / pr-title / sop-lock / unittest 里调用 `forge release`
