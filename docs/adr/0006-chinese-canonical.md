# 0006 中文为权威语言

- 状态：已接受
- 日期：2026-09-11

## 背景

v1 的 README 以英文为主，中文是翻译页；设计文档中英混排。接入方和 agent 需要一份权威说明。工具仓不是某一家产品仓，通用文档里也不该夹产品口音（产品仓路径、生产域名、某一家构建 workflow 的名字）当作默认例子。

## 决定

- **中文是权威。** 新写的设计、ADR、CHANGELOG、迁移、SOP、契约文档用中文。
- **英文只保留 `README.md` 一页入口**（30 秒用途、安装、三条命令、链到中文权威文档）。`README.zh-CN.md` 保留文件名，作为中文主入口。两者互链。
- 代码注释与错误信息可以英文。
- 去口音：通用说明用「产品仓」「保护分支」「agent 分支前缀」「CI job 名」「产品命令」。`LearningGuidePortal` / 生产域名 / 某一家构建检查名只许出现在 `examples/learning-guide/`、明确标为示例的地方、ADR/CHANGELOG 的历史叙述，以及程序锁需要点名的禁令（例如内核不得出现该域名）。
- 叶子标题必须是 `### Functional` / `### Negative` / `### Edge`（技法名保持英文，与契约一致）。

## 后果

- Agent 冷启动：英文 README 够跑通三条命令；规则与契约读中文。
- `gh skill install` 的 host id 仍是 `codex` / `cursor` / `claude-code` / `github-copilot`（这是 GitHub CLI 的机器名，不是口音）。
- 工作本 `AGENTS.md` 缩成入口：硬规则 → STATE → 登记/ADR → skills。

## 替代方案

- 全英文权威、中文翻译：否。拥有者已定中文权威。
- 双语每篇对照：成本高，漂移快。入口互链即可。
