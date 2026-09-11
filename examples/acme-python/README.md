# Acme Python — 最小非口音接入示例

产品仓只留薄配置。工具在旁边的工作本（`PYTHONPATH`）。不要 vendor `forge/` 或 `overlay/`。

本地：

```text
export PYTHONPATH=/path/to/AIOps
python3 -m overlay validate --root examples/acme-python
python3 -m overlay cover --root examples/acme-python
python3 -m forge check --root examples/acme-python
python3 -m unittest discover -s tests -q
```

`product_command` 与上面最后一条相同。CI 用 reusable `overlay.yml` + `setup_command`。
