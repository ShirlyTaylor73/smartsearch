## Why

当前 CLI 将 provider 名称、路由策略和研究编排直接暴露为大量顶层命令，迫使 Agent 理解底层供应商差异并参与 fallback 决策，增加了工具选择和上下文负担。新版 CLI 应以稳定的搜索能力为公开契约，把 provider 选择、顺序和故障转移收回配置与内部服务层。

## What Changes

- 将 Agent 可见的搜索命令收敛为 `search`、`docs`、`fetch`、`map` 四类能力，分别覆盖通用网页搜索、代码/技术文档查询、已知 URL 详细内容抓取和指定网站结构探索；其中 `docs` 通过 provider 无关的 `search`、`tree`、`read` 子命令表达文档搜索、仓库结构和文件读取三种不同操作。
- 为四类命令定义统一、与 provider 无关的参数和输出契约；默认输出只包含 Agent 完成任务所需的内容、来源和错误信息。
- 由配置文件定义每类能力启用的 provider、优先级、超时与 fallback 策略，CLI 自动按能力链执行，Agent 不得通过普通查询参数选择 provider。
- 保留 `-h/--help`、`-v/--version`、`setup`、`config`、`doctor`、`diagnose` 等面向人类维护者的功能性入口，并将详细 provider 尝试信息限制在诊断或 debug 输出中。
- **BREAKING**：provider 专用顶层查询命令、`--providers`、`--fallback` 等 Agent 可见控制项不再属于新版公开契约；迁移期内如保留兼容入口，必须从默认帮助和 Agent skill 中隐藏并输出弃用提示。
- **BREAKING**：移除 `deep`、`research` 命令及其离线规划、live research、证据目录和研究综合实现；研究分解、循环检索和最终写作由上层 Agent 负责。
- **BREAKING**：移除 AnySearch provider、`anysearch-domains`、`anysearch-search`、`anysearch-extract`、`anysearch-batch`、相关配置与垂直搜索路由。未来的论文与垂直检索将在独立 change 中通过更强的 paper-search 能力扩展，本期不提供替代实现。
- **BREAKING**：`route`、`route-calibrate`、`smoke`、`regression`、`model` 等不再作为 Agent 搜索命令宣传；维护或开发能力应归入非 Agent 文档、诊断入口或测试脚本。

## Capabilities

### New Capabilities

- `agent-search-commands`: 定义 `search`、`docs search|tree|read`、`fetch`、`map` 四类 Agent 可见搜索能力的用途、输入、统一输出和边界。
- `configured-provider-routing`: 定义按能力配置 provider 链、自动 fallback、错误分类、结果归一化和 provider 信息隐藏规则。
- `cli-operations`: 定义帮助、版本、初始化、配置管理、健康检查、专项诊断、debug 输出及旧命令迁移规则。

### Modified Capabilities

无。当前 OpenSpec 主规格目录中没有可复用的既有 capability，本次建立新版 CLI 的首批规格。

## Impact

- 主要影响 `src/smart_search/cli.py`、`src/smart_search/service.py`、`src/smart_search/config.py`、provider contract、CLI 测试及中英文 README。
- 删除 `src/smart_search/providers/anysearch.py`、Deep Research 规划与执行路径，以及对应测试、配置字段、README 和 skill 引用。
- `skills/smart-search-cli/` 与 `src/smart_search/assets/skills/smart-search-cli/` 的 Agent 指令必须同步收敛为四类搜索能力，并准确说明 `docs search|tree|read`。
- 需要为仍有同等新操作的旧命令和参数制定明确的兼容窗口；AnySearch 与 Deep Research 直接删除，不进入兼容转发层。
- Context7、Exa、Zhipu MCP zread 的不同工具必须映射到 `docs` 的同操作能力链，不能用文档搜索结果冒充仓库结构或文件内容。
