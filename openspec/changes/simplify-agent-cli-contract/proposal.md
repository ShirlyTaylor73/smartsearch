## Why

当前 CLI 将 provider 名称、路由策略和不同类型的查询操作混合为大量顶层命令，迫使 Agent 理解底层供应商差异并承担 fallback 决策。新版 CLI 应在不损失现有有效能力的前提下，以四大能力命名空间组织操作，把 provider 选择、顺序和故障转移收回配置与内部服务层。

## What Changes

- 将 Agent 可见的查询接口收敛为四大能力命名空间：
  - `search answer|sources|similar`
  - `docs resolve|search|tree|read`
  - `fetch content|extract`
  - `map site`
- 将现有主模型回答、Exa/智谱/Tavily/Firecrawl 来源发现、Exa Similar、Context7 library/docs、Zhipu MCP zread、网页 Reader/Scrape、结构化抽取和 Tavily Map 无损映射到相应 operation。
- `search sources` 保留 provider 无关的结果数量、检索模式、时间、域名、category、正文和 highlights 等过滤参数；系统根据参数要求筛选支持该 operation/feature 的 provider，而不是由 Agent 点名 provider。
- 配置文件按 `capability.operation` 定义 provider、优先级、禁用项、超时和 fallback；fallback 严格限制在相同 operation 内。
- 将诊断与开发功能整理为 `diagnose search|docs|fetch|map|provider|route|route-calibrate|smoke` 和 `dev regression`，保留 `setup`、`doctor`、`config`、`skills`、`-h/--help`、`-v/--version`。
- **BREAKING**：provider 专用顶层查询命令、`--providers`、`--fallback` 等 Agent 可见控制项不再属于新版公开契约；有同等新 operation 的旧命令在一个发布周期内隐藏兼容并提示迁移。
- **BREAKING**：移除 AnySearch provider、`search vertical|domains|batch`、旧 AnySearch 命令、相关配置与 `vertical_search` 路由。未来论文和垂直检索通过独立的 paper-search change 扩展。
- **BREAKING**：移除 `deep`、`research` 及其离线计划、live research、证据目录和研究综合实现；上层 Agent 使用四大能力自行编排研究过程。

## Capabilities

### New Capabilities

- `agent-search-commands`: 定义四大能力命名空间及其无损 operation、参数、统一输出和边界。
- `configured-provider-routing`: 定义 `capability.operation` provider 声明、feature 匹配、同操作 fallback、结果归一化和 provider 信息隐藏规则。
- `cli-operations`: 定义帮助、版本、初始化、配置、健康检查、完整诊断树、开发命令、debug 输出及旧接口迁移规则。

### Modified Capabilities

无。当前 OpenSpec 主规格目录中没有可复用的既有 capability，本次建立新版 CLI 的首批规格。

## Impact

- 主要影响 `src/smart_search/cli.py`、`src/smart_search/service.py`、`src/smart_search/config.py`、provider contract、CLI/服务测试及中英文 README。
- 删除 `src/smart_search/providers/anysearch.py`、Deep Research 规划与执行路径，以及对应测试、配置字段、README 和 skill 引用。
- Context7、Exa、Zhipu MCP、Tavily、Jina 和 Firecrawl 的现有入口需要迁移到 operation executor；Firecrawl 需要为 `fetch.extract` 提供结构化输出路径或在不可用时返回明确能力错误。
- `skills/smart-search-cli/` 与 `src/smart_search/assets/skills/smart-search-cli/` 必须同步为四大能力及其子命令，不再教授 provider 专用命令。
- 需要为仍有同等新 operation 的旧命令制定隐藏兼容窗口；AnySearch 与 Deep Research 直接删除，不进入兼容转发层。
