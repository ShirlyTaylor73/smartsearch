## Why

当前 CLI 通过同一 operation 下的多 provider 候选、feature negotiation 与 fallback 隐藏供应商差异，但不同供应商的参数和结果语义并不完全等价，导致适配层复杂、诊断困难，也可能静默降低调用约束。应改为由配置确定的最小固定 provider 集合，使每个 Agent 可见子命令都有唯一、可预测的执行方。

## What Changes

- 将公开查询 operation 固定映射到五类 provider：Grok、Exa、Context7、Zhipu MCP ZRead、Firecrawl；Agent 仍只选择任务子命令，不选择 provider。
- 明确唯一职责：`search answer` → Grok，`search sources` → Exa，`docs resolve` 与普通 `docs search` → Context7，仓库定向 `docs search --source owner/repo` 及 `docs tree|read` → Zhipu MCP ZRead，`fetch content|extract` 与 `map site` → Firecrawl。
- `search sources` 使用 Exa 当前推荐的 `type=auto`，删除 Agent 可见的 `--mode semantic|keyword|auto`；如需选择 Exa 原生的速度/深度类型，只能通过配置文件完成。
- `search answer` 保留 xAI Responses 与 OpenAI-compatible 两种 Grok 接入格式，但由配置二选一，不互相 fallback。
- `docs search` 根据是否提供仓库来源约束进行确定性分流，而不是构建 provider 候选链。
- **BREAKING**：移除跨 provider fallback、provider order、feature negotiation、disabled candidate 及相应运行时配置；唯一 provider 未配置、参数不受支持或请求失败时立即返回统一错误。
- **BREAKING**：移除 Tavily、Jina、Zhipu REST API、Zhipu MCP Search/Reader、DeepWiki 及其凭据、命令兼容入口、诊断项和文档，只保留 Zhipu MCP ZRead。
- **BREAKING**：`docs tree`、`docs read` 删除 ZRead 不支持的 `--ref`；`docs search --source` 调用 ZRead `search_doc` 时按请求或配置传递 `language`。
- **BREAKING**：`map site` 从 Tavily Map 迁移到 Firecrawl Map，删除 `--instructions`、`--max-depth`、`--max-breadth`，改为 Firecrawl 可表达的站点映射参数。
- **BREAKING**：删除 `search similar`。Exa 官方 Python SDK 已将 `find_similar()/findSimilar` 标记为 deprecated，并建议使用 Search；当前官方 API Reference 也不再公开该 endpoint。
- **BREAKING**：删除 `search sources --mode`。Exa 当前 Search `type` 为 `instant|fast|auto|deep-lite|deep|deep-reasoning`，不再提供可与 `semantic|keyword` 无损对应的 `neural|keyword` 枚举。
- 更新 `doctor`、`diagnose`、`setup`、`config`、README 与两份 Agent skill，使其只展示固定映射、凭据状态和可执行的错误排查路径。
- 以 `0.3.0-beta.x` 作为破坏性迁移版本线，并删除会把旧 provider 命令转发到不同 provider 的兼容行为。

## Capabilities

### New Capabilities

- `minimal-provider-cli-contract`: 定义四大能力命令树、每个子命令的唯一 provider、公开参数、输出和破坏性迁移边界。
- `deterministic-provider-routing`: 定义固定 operation 路由、配置二选一、无 fallback 失败语义、凭据与诊断契约。

### Modified Capabilities

无。当前 `openspec/specs/` 尚无已同步的主规格；本 change 将替代先前 change 中尚未同步的多 provider routing 设计。

## Impact

- 主要影响 `src/smart_search/cli.py`、`service.py`、`config.py`、provider registry/adapter、统一输出与错误类型。
- 删除未进入最小覆盖集的 provider 模块、配置字段、环境变量读取、测试 fixture 与兼容命令；保留并收紧 Grok、Exa、Context7、Zhipu MCP ZRead、Firecrawl。
- Firecrawl adapter 需要覆盖 Scrape、JSON Schema extraction 与 Map；Exa adapter 只承接当前 `/search` 及其公开过滤参数，不再调用 deprecated `/findSimilar`。
- CLI/服务/provider/config 测试、`README.zh-CN.md`、`README.md`、`skills/smart-search-cli/` 与包内发布副本必须同步更新。
- 这是公开 CLI、配置与凭据契约的破坏性变更，需要迁移说明、版本升级和真实 provider smoke 验证记录。
- Provider 契约核对以 Exa Search API、Exa 官方 Python SDK、Firecrawl Scrape/Map 和 ZRead MCP 官方文档及实时 `tools/list` 为依据。
