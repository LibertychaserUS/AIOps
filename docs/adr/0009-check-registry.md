# 0009 check 注册表：封闭、有序、可契约测试

- 状态：已接受（2026-11-06，维护者决定）
- 日期：2026-11-06

## 背景

`forge check` 的十步清单原先全部写在 `forge/check.py` 一个 `run_check` 函数里，`forge.yaml` 的数据模型住在 `forge/apply.py`，git 助手（`_git`、`resolve_protect_ref`、`list_changed_paths`、`current_branch`）在 `check.py` / `status.py` / `ci_select.py` / `title.py` 各有一份。加一把锁要改四处：清单函数里插一段、各自重新 `load_config`、各自重新算一遍 diff、文档和测试靠人记。三条纪律——「没有 `forge.yaml` 则 skip」「看不到 base 则红」「git 不可用退出 2 而不是抛栈」——每一步各写一遍，漏一处就是假绿（`test_false_greens.py` 里的每一条都曾经是这样绿过的）。

另一个诱惑是把门做成插件：扫目录、读 entry points、在 `forge.yaml` 里让接入方声明自己的 check，甚至从远端拉钩子。这是反模式：能让「我们」直接拓展的机制，也能让 agent 直接拓展；门里跑可配置代码，等于把锁的钥匙放在被锁的 PR 里。

## 决定

1. **封闭注册表。** `forge/checks/` 是一个包：每个 check 一个模块（`overlay.py`、`spec.py`、`deny_paths.py`、`suite_guard.py`、`docs_sync.py`、`sop_lock.py`、`schema.py`、`unittest_.py`），`forge/checks/__init__.py` 里 `CHECKS: tuple[Check, ...]` 是**显式有序元组**。顺序就是清单顺序，也是依赖顺序：`deny_paths` 与 `suite_guard` 共用一份 diff，`pr-title` 在 `pr-body` 前共用一次事件判定。不扫目录、不用 `importlib` / `pkgutil` / entry points、不读配置里的代码。接口只有一个 `CheckContext` dataclass 和一个 `Check` 协议（`name` / `needs` / `applies` / `run`），不做基类层级、生命周期钩子、事件总线。
2. **runner 统一纪律。** `forge/check.py` 只剩 runner：一次 `load_config`、一次 `resolve_protect_ref`、一次 `list_changed_paths` 装进 `CheckContext`，按 `CHECKS` 跑。模块用 `needs` 声明依赖即继承：`forge.yaml`（缺则 `skip  no forge.yaml`，读不了则红并带出配置错误）、`git`（git 不在 PATH 时该行红、退出 2，不抛栈）、`base`（看不到 base 的 check 不得绿；用 `no_base_detail` 的那句红）。
3. **配置开关，不是配置代码。** 接入方能开关的是 `forge.yaml` 已有字段（`deny_paths`、`docs_sync`、`title.scopes`、`agent_branch_prefixes`……）。接入方**不能**在 `forge.yaml` 里声明自定义 check；要加自己的门，走 GitHub required checks（`branches.<name>.required_checks` 写 CI job 名），那是 Ruleset 层的事，不是 `forge check` 的事。
4. **契约测试。** `tests/forge/test_checks_registry.py` 钉住：每个注册的 check 名字唯一非空；顺序等于文档清单；`tests/forge/` 有提到该名字的测试；`docs/cli.md` 或 `docs/forge-config.md` 有对应行；对只有 `forge.yaml` 的非 git 临时根，runner 返回 `Step` 而不抛异常；`CHECKS` 是元组；注册表源码没有 `importlib` / `pkgutil` / `entry_points`。`sop-lock`（仅工作本根）对最后一条再锁一次。
5. **同一刀的搬家。** `forge/config.py` 收下 `ForgeConfig` / `BranchRule` / `DocsSyncRule` / `ForgeError` / `load_config` / `validate_config` / 严格 PyYAML loader / 键白名单；`forge/gitutil.py` 收下 git 助手一份；`forge/pathmatch.py` 收下 `deny_paths` 与 `docs_sync.paths` 共用的匹配器。`apply.py` / `check.py` / `title.py` 原样 re-export，旧 import 路径全部保留。`GitHubClient` 暂留 `apply.py`（刚在 #19 重做过，下一刀再搬）。

## 后果

- 加一个 check 是四件事，缺一不合：`forge/checks/<name>.py` 一个模块；`CHECKS` 元组加一项（位置即顺序）；`tests/forge/` 一个提到该名字的测试；`docs/forge-config.md`（或 `docs/cli.md`）一行。契约测试会把漏掉的那件点名。
- 新 check 不必再自己写三条纪律，声明 `needs` 即可；也不能再「忘记」它们。
- 行为零变化：`forge check` 清单与 `apply --dry-run` 输出逐字节一致，测试数只增不减。这是重构的验收标准，也是以后每一刀的验收标准。
- 「可拓展」与「锁」不矛盾的四个条件：注册表在源码树内、显式元组、`forge/**` 在 CODEOWNERS、`sop-lock` 断言没有运行时发现。少一条就回到插件。
- 非目标（要另写 ADR）：agent 身份只看分支名（改名就绕过 `suite_guard`，长期应按 token 身份）；配置按段校验与 Ruleset 规则表（设计稿第 2、3 步）各自一个 PR。

## 替代方案

- **pre-commit 式插件**（`repos:` 列表拉外部钩子）：否。钩子代码从 PR 自己带的配置里来，门被门锁住的东西改写；且本地 hook 不是合入锁（见 [`sop-lock.md`](../sop-lock.md)，不装 husky 同理）。
- **Danger / Dangerfile**（在 PR 里跑一段脚本决定红绿）：否。同上，脚本在 PR 里；而且 `forge check` 要在本地与 CI 跑出同一张清单，不依赖 PR 上下文。
- **OPA / Rego 策略引擎**：否。多一门语言、多一个二进制，锁的可判定子集现在用 CPython 单测就能钉住；接入方要的是「我的 CI job 名写进 required checks」，不是策略语言。
- **entry points / 目录扫描自动发现**：否。丢顺序，丢「这把锁为什么在这」，让安装环境决定清单内容；契约测试也无从比对。
- **保持现状，继续在 `run_check` 里加 `if`**：否。第十一把锁仍要改四处，三条纪律仍靠人记。本 ADR 的代价是一张接口（一个 dataclass、一个协议、一个元组），不是一套框架。
