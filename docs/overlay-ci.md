# Overlay CI

产品仓如何调用 Overlay 的 reusable workflow。契约见 [`overlay-contract.md`](overlay-contract.md)。

## reusable workflow

工具仓提供 `.github/workflows/overlay.yml`（`workflow_call`）。产品仓写一个薄的 `overlay-check.yml` 调用它，**不要**把 `overlay/` 拷进产品仓。

`overlay-check` 必须是 GitHub Checks 上的 **CI job 名**（check name），不要抄工具仓自己的 workflow 文件名。

### 最小调用

```yaml
# .github/workflows/overlay-check.yml  — 写在产品仓
name: overlay-check
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  overlay:
    uses: <tool-repo>/.github/workflows/overlay.yml@overlay-v2.0.0
    with:
      enable_run: true
      root: "."
```

`<tool-repo>` 是提供 Overlay 的仓库（本工作本或其 fork）。`tool_ref` 可覆盖 pin。永远 pin 已发布的 tag 或 SHA，不要 pin `main`。

若产品仓已经有能跑的 inline `overlay-check`（checkout 同一 pin 再跑 `python -m overlay`），不要换成另一种形状。

### `--branch` 缺省

reusable 的 `branch` 输入默认为空。workflow 内解析顺序：

1. `inputs.branch`（调用方显式传入）
2. `github.base_ref`（pull_request 的基线）
3. `github.ref_name`

这与 CLI `python -m overlay select` 的缺省一致：`GITHUB_BASE_REF` → `GITHUB_REF_NAME` → `main`。未知分支再按 `overlay.yaml` 回落到 `branches.default` 再到 `main`。

本工作本的 `overlay-check.yml` 把 `branch: main` 写死，是为了在 agent 分支上仍跑工具仓自己的 Overlay 套件，不是通用默认。

## `setup_command`（runtime setup）

`run` job 在执行 `product_command` 之前，若 `setup_command` 非空，会在**调用方（产品）checkout**里跑该 shell。`validate` / `select` 不会跑它。

这只安装产品工具链，不是安全边界。

### Node

```yaml
jobs:
  overlay:
    uses: <tool-repo>/.github/workflows/overlay.yml@overlay-v2.0.0
    with:
      enable_run: true
      setup_command: npm ci
```

### Python

```yaml
jobs:
  overlay:
    uses: <tool-repo>/.github/workflows/overlay.yml@overlay-v2.0.0
    with:
      enable_run: true
      setup_command: pip install -r requirements-dev.txt
```

### Go

```yaml
jobs:
  overlay:
    uses: <tool-repo>/.github/workflows/overlay.yml@overlay-v2.0.0
    with:
      enable_run: true
      setup_command: go mod download
```

### Java

```yaml
jobs:
  overlay:
    uses: <tool-repo>/.github/workflows/overlay.yml@overlay-v2.0.0
    with:
      enable_run: true
      setup_command: mvn -B -q -DskipTests dependency:go-offline
```

需要多步时，把命令写成一行（`&&` 连接），或改用产品仓自己的 inline job。

## 本地等价

```text
python3 -m overlay validate --root .
python3 -m overlay cover --root .
python3 -m overlay select --root . --write-receipt receipts/
python3 -m overlay run --root . --workdir . --write-receipt receipts-run/ --timeout 600
```

产品仓旁放工具仓时设 `PYTHONPATH=<tool-checkout>`。`select` / `run` 不传 `--branch` 时走环境变量缺省。

## 不要

- 不要在 push 上跑 `overlay generate`。
- 不要另开 unittest workflow 绕过 Overlay select。Overlay 测试写进 `active` 套件的 `product_command`。Forge 单测走 `forge-check`。**通用检查 ≠ 产品门。**
- 不要 `workflow_call` 产品仓自己的构建 workflow。
- `forbid_hosts` 只是字符串匹配，防手滑，不是安全边界。
