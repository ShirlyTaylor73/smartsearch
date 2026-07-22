## Context

`simplify-agent-cli-contract` 已把查询入口整理为 `search`、`docs`、`fetch`、`map` 四大能力，但其实现仍通过 `OPERATION_PROFILES`、`PROVIDER_OPERATION_FEATURES`、`SMART_SEARCH_OPERATION_CONFIG` 和 fallback runner 为同一 operation 维护多个候选。当前 provider 的请求参数、内容质量和失败语义并不等价，统一 feature 后再 fallback 会扩大适配与测试矩阵，也会让“同一个命令”在不同环境产生不同语义。

本变更保留任务级 CLI，不再追求 provider 可互换。配置者只负责提供最小覆盖集的凭据并选择 Grok 接入格式；Agent 不接触 provider。公开 JSON/Markdown/content 输出继续作为稳定契约，敏感配置与原始异常不得泄漏。

实现必须以当前官方文档为准，尤其是 Exa Search、Firecrawl Scrape/JSON/Map、Context7 API 和 Zhipu Coding Plan ZRead MCP。Exa 当前 Search `type` 为 `instant|fast|auto|deep-lite|deep|deep-reasoning`，官方 SDK 已将 `find_similar()/findSimilar` 标记为 deprecated。ZRead 实时 `tools/list` 确认工具 schema 为 `search_doc(repo_name, query, language?)`、`get_repo_structure(repo_name, dir_path?)`、`read_file(repo_name, file_path)`，其中 `language` 只接受 `zh|en`，三个工具均不接受 `ref`。

## Goals / Non-Goals

**Goals:**

- 为每个公开 operation 指定唯一 provider/tool，消除运行时 provider 候选链。
- 继续让 Agent 只表达任务动作，provider 与凭据仅由配置、doctor 和 diagnose 处理。
- 保留四大能力下现有有效子命令与统一输出，不因删除 provider 而删除被固定 provider 覆盖的任务能力。
- 对 Exa、ZRead、Firecrawl 的真实参数约束进行显式校验，不静默忽略参数。
- 把 breaking CLI/config/provider 迁移拆成可测试、可回滚的阶段，并同步中英文文档和两份 skill。

**Non-Goals:**

- 不提供同 operation 的备用 provider，也不允许用户配置 provider 顺序。
- 不恢复 AnySearch、垂直搜索、Deep Research 或 paper-search；论文垂直检索由后续独立集成处理。
- 不用 DeepWiki 替代 ZRead，也不保留 Tavily、Jina、Zhipu REST Search、Zhipu MCP Web Search/Reader。
- 不保证删除的 provider 专用旧命令继续可用。
- 不把 provider 专有响应直接暴露为公共输出。

## Decisions

### 1. Operation 使用固定责任矩阵

| CLI capability | 公开子命令 | 唯一 provider | provider operation/tool | 路由条件 |
|---|---|---|---|---|
| `search` | `answer QUERY` | Grok | 配置选择 xAI Responses API 或 OpenAI-compatible Chat Completions | `SMART_SEARCH_GROK_TRANSPORT` 二选一 |
| `search` | `sources QUERY` | Exa | `/search` | 无 |
| `docs` | `resolve NAME [QUERY]` | Context7 | library resolve/search | 无 |
| `docs` | `search QUERY` | Context7 | docs/context lookup | 未提供 `--source`，或 source 为 Context7 library id |
| `docs` | `search QUERY --source owner/repo` | Zhipu MCP ZRead | `search_doc` | source 符合 GitHub `owner/repo` 形式 |
| `docs` | `tree REPO [--path PATH]` | Zhipu MCP ZRead | `get_repo_structure` | 无 |
| `docs` | `read REPO PATH` | Zhipu MCP ZRead | `read_file` | 无 |
| `fetch` | `content URL` | Firecrawl | Scrape，Markdown/正文 format | 无 |
| `fetch` | `extract URL` | Firecrawl | Scrape，JSON Schema format | 无 |
| `map` | `site URL` | Firecrawl | Map | 无 |

“唯一 provider”表示一次 operation 只会调用表中 provider。Grok 的两个 transport 是同一回答能力的部署格式，由配置明确选择；系统不得因一个 transport 失败而尝试另一个。相同 provider 内针对 408/429/5xx/网络瞬断的有限重试可以保留，但重试必须使用同一 endpoint、同一 operation 和等价参数，并受统一超时预算约束。

选择固定矩阵而不是继续 feature negotiation，是因为它能让参数是否生效在调用前确定，也把 live smoke 测试数量从 provider 组合矩阵降为每个 operation 一条主路径。代价是单点故障时立即失败，这是本设计接受的显式行为。

`search similar` 不进入新版矩阵。Exa 官方 SDK 已明确将 `findSimilar` 标记为 deprecated 并建议改用 Search，但普通 Search 接受文本 query，不能保证与“给定 URL 查找内容相似页面”语义等价，因此本变更直接删除该子命令，不做误导性转发。

### 2. Grok transport 由单一配置键选择

新增 `SMART_SEARCH_GROK_TRANSPORT`，允许值为 `xai-responses` 或 `openai-compatible`。setup 必须要求选择其一：

- `xai-responses` 使用 `XAI_API_URL`、`XAI_API_KEY`、`XAI_MODEL`、`XAI_TOOLS`。
- `openai-compatible` 使用 `OPENAI_COMPATIBLE_API_URL`、`OPENAI_COMPATIBLE_API_KEY`、`OPENAI_COMPATIBLE_MODEL`、`OPENAI_COMPATIBLE_STREAM`。

若两个凭据集合都存在，仍只使用配置选中的 transport；若选中项不完整，`search answer` 返回 `config_error`，不探测另一组凭据。删除 `OPENAI_COMPATIBLE_FALLBACK_MODELS`、`SMART_SEARCH_FALLBACK_MODE` 及主搜索 provider 列表。公开 `search answer` 保留 `QUERY`、`--timeout`、`--debug` 和通用输出参数；删除会把 transport 细节暴露给 Agent 的 `--stream/--no-stream`，stream 由 `OPENAI_COMPATIBLE_STREAM` 配置。

### 3. `docs search` 使用可判定的 source 语义

`docs search` 不构建候选链：

- source 为空：先由 Context7 resolve query，再调用 Context7 docs。
- source 为 Context7 library id（例如 `/vercel/next.js` 或 Context7 返回的稳定 id）：直接调用 Context7 docs。
- source 为规范化 GitHub `owner/repo`：调用 ZRead `search_doc(repo_name, query, language?)`。
- source 既不是有效 library id 也不是 `owner/repo`：在发出网络请求前返回 `parameter_error`。

由于 `/owner/repo` 形式可能同时像 Context7 id，CLI 应优先识别显式 Context7 id 的格式/来源；README 必须指导普通库文档先运行 `docs resolve` 并复用返回 id，GitHub 仓库则使用不带前导 `/` 的 `owner/repo`。ZRead 的 `language` 不新增 Agent 必填项：服务层根据 query 是否包含中文字符推导 `zh` 或 `en`，无法判断时使用配置默认值，并只传递实时 `tools/list` 确认的 `zh|en`。

### 4. 每个子命令只公开唯一 provider 可兑现的参数

| 子命令 | 公开任务参数 | 适配规则 |
|---|---|---|
| `search answer` | `QUERY`、`--timeout` | 由选定 Grok transport 执行 |
| `search sources` | `QUERY`、`--limit`、`--start-published-date`、`--include-domains`、`--exclude-domains`、`--category`、`--include-text`、`--include-highlights` | 一一映射 Exa Search；Search `type` 默认使用官方推荐的 `auto`，不由 Agent 参数控制 |
| `docs resolve` | `NAME [QUERY]` | 映射 Context7 library resolve |
| `docs search` | `QUERY [--source SOURCE]` | 按上一决策确定性选择 Context7 或 ZRead |
| `docs tree` | `REPO [--path PATH]` | `--path` 映射 ZRead `dir_path`；删除 `--ref` |
| `docs read` | `REPO PATH` | 映射 ZRead `file_path`；删除 `--ref` |
| `fetch content` | `URL` | Firecrawl Scrape 请求 Markdown/正文 |
| `fetch extract` | `URL`、`--schema JSON`、`--max-length N` | Firecrawl Scrape 请求 JSON format；`--max-length` 只限制返回的 `raw_evidence`，不截断 `data` |
| `map site` | `URL`、`--search TEXT`、`--sitemap include|skip|only`、`--include-subdomains/--no-include-subdomains`、`--ignore-query-parameters/--no-ignore-query-parameters`、`--ignore-cache`、`--limit N`、`--timeout SECONDS`、`--location JSON` | 一一映射 Firecrawl Map；秒制 timeout 转为毫秒，location 仅接受 `country` 与 `languages` |

所有 operation 继续支持 `--debug`、`--format json|markdown|content`、`--output PATH` 等公共功能参数。`search sources` 删除 `--mode`，避免把 Exa 已内置的检索策略错误描述为可切换的 semantic/keyword；维护者如需控制速度/深度，可通过 `EXA_SEARCH_TYPE` 选择 Exa 当前原生枚举，默认 `auto`。`map site` 删除 Tavily 专有的 `--instructions`、`--max-depth`、`--max-breadth`；迁移文档给出 `--search` 和 Firecrawl sitemap/subdomain 参数的替代示例。CLI 不接受后再静默丢弃任何 provider 不支持的参数。

Firecrawl Map 使用官方默认值：`sitemap=include`、`includeSubdomains=true`、`ignoreQueryParameters=true`、`ignoreCache=false`、`limit=5000`；limit 必须处于 `1..100000`。CLI 的 `--timeout` 使用秒以保持人类可读性，adapter 转为官方要求的毫秒；location 的 `country` 必须为大写 ISO 3166-1 alpha-2，`languages` 必须为字符串数组。

### 5. 删除通用 provider registry，保留 operation executor

`OPERATION_PROFILES` 从“provider 列表 + feature 集合”收敛为不可由配置重排的 operation descriptor：固定 executor、必需配置键、默认 timeout 和输出 normalizer。删除 `PROVIDER_OPERATION_FEATURES`、`operation_candidates()`、`_run_operation_candidates()` 及 fallback attempt 聚合。

统一 envelope 继续包含 `ok`、`capability`、`operation`、`content`、`sources`、`elapsed_ms`；operation 特有字段继续使用 `results`、`candidates`、`entries`、`data`、`raw_evidence`。普通输出删除 `provider_attempts`、`fallback_used` 等字段；`--debug` 可增加单个脱敏 `provider`、`provider_operation`、request id 和 timing，但不得包含 token、完整 endpoint query 或异常堆栈。

### 6. 配置只描述 endpoint、凭据和固定 operation timeout

删除 `SMART_SEARCH_OPERATION_CONFIG` 中的 `providers`、`disabled`、`fallback` 与 feature 配置，并删除 `SMART_SEARCH_FALLBACK_MODE`。允许保留固定 operation 的 timeout override，但其结构只接受已知 operation → timeout，不接受 provider 名称或顺序；若沿用原键会造成歧义，应迁移为 `SMART_SEARCH_OPERATION_TIMEOUTS`。

保留的主要凭据为：

- Grok：选定 transport 对应的一组 XAI 或 OpenAI-compatible 配置。
- Exa：`EXA_API_KEY`、`EXA_BASE_URL`、`EXA_TIMEOUT_SECONDS`、`EXA_SEARCH_TYPE`；最后一项只允许当前官方枚举且默认 `auto`。
- Context7：`CONTEXT7_API_KEY`、`CONTEXT7_BASE_URL`、`CONTEXT7_TIMEOUT_SECONDS`。
- ZRead：`ZHIPU_MCP_API_KEY`、`ZHIPU_MCP_ZREAD_API_URL`、`ZHIPU_MCP_TIMEOUT_SECONDS`。
- Firecrawl：`FIRECRAWL_API_KEY`、`FIRECRAWL_API_URL`，并增加明确的 timeout 配置（若当前没有独立字段）。

删除 Tavily、Jina、Zhipu REST、Zhipu MCP Search/Reader 的配置键和 setup 问题。读取旧 config 文件时，未知旧键不得影响启动；`config list` 不再展示它们，迁移说明提示用户手动 `config unset` 清理。

### 7. 失败立即终止并保持统一分类

固定 provider 缺少凭据时返回 `config_error`；CLI 参数/schema/source 无效时返回 `parameter_error`；认证失败返回 `auth_error`；429 返回 `rate_limited`；超时返回 `timeout`；网络/5xx 返回 `network_error`；provider 返回不可解析内容时返回 `provider_error` 或 `parse_error`。任何失败都不得调用其他 provider 或其他 operation。

同 provider 的有限重试结束后只返回最终统一错误。错误消息必须包含 operation、缺失配置或建议的 diagnose 命令，但不建议 Agent 改用已删除的 provider 专用命令。

### 8. Diagnose 与 doctor 展示责任而不改变路由

保留完整维护树：`diagnose search|docs|fetch|map`、`diagnose provider`、`diagnose route`、`diagnose route-calibrate`、`diagnose smoke`，以及 `doctor`。operation diagnose 输出固定 `responsible_provider`、必需配置状态、endpoint connectivity 和参数/schema 检查，不再输出候选、顺序、single-provider 或 fallback 状态。

`diagnose provider` 只允许 Grok 的两个 transport、Exa、Context7、Zhipu MCP ZRead 和 Firecrawl。`doctor` 按责任矩阵列出全部 operation；同一凭据覆盖多个 operation 时仍逐项报告 executor 是否完整。search diagnose 只包含 `answer|sources`，不得继续展示 `similar`。route/route-calibrate 仅作为查询意图调试保留，不参与已明确 operation 的 provider 选择。

### 9. 删除 provider 专用兼容入口

旧 `exa-search`、`exa-similar`、Context7、Zhipu、Zhipu MCP、Tavily、Jina、旧 `fetch`/`map` provider 形态不再隐藏转发。`exa-search` 的迁移目标是 `search sources`；`exa-similar` 与 `search similar` 一并删除且没有语义等价替代。继续转发会把旧命令语义悄悄改为另一个 provider，违背确定性契约。AnySearch 和 Deep Research 仍保持已删除状态。

## Risks / Trade-offs

- [唯一 provider 故障会使 operation 不可用] → doctor、operation diagnose 和 live smoke 提前发现；运行时返回明确错误，不伪装降级。
- [Exa 或 Firecrawl 官方 schema 变化] → adapter 层集中维护请求/响应映射，契约测试固定 outbound payload，并在相关修改中对照官方文档。
- [删除 Exa Similar 会减少一个查询动作] → 明确 deprecated endpoint 没有可靠等价替代；未来只有在 Exa 提供新的官方相似检索契约时才通过独立 change 恢复。
- [`docs search --source` 形式可能歧义] → 定义 Context7 id 与 `owner/repo` 的规范形式，先本地校验并在帮助中提供 resolve 工作流。
- [删除 `--ref` 降低仓库精确版本能力] → 明确这是 ZRead 当前能力边界；未来若 provider 官方增加 ref，再通过独立 change 恢复。
- [Firecrawl Map 与 Tavily Map 参数不兼容] → 作为 breaking change 删除旧参数，提供参数迁移表和 parser 回归测试。
- [删除旧 config 键影响已有安装] → 旧键读取时忽略但不执行；setup/doctor 给出一次性清理提示，配置文件位置不变。
- [固定矩阵未来需要扩展] → 新 provider 必须通过新的 OpenSpec change 替换某 operation 或增加新 operation，不恢复任意候选链。

## Migration Plan

1. 先添加 CLI 参数、固定责任矩阵、无 fallback、删除 `search similar/--mode`、ZRead schema 和 Firecrawl Map 的失败测试。
2. 引入确定性 operation descriptor 与 `SMART_SEARCH_GROK_TRANSPORT`，迁移 `search` 与 `docs` executor。
3. 扩展 Firecrawl adapter 覆盖 content、JSON extract、Map，并迁移 `fetch`、`map`。
4. 删除 provider registry/fallback/feature negotiation 和被淘汰 provider 代码、配置、诊断及测试。
5. 重做 setup、doctor、diagnose、help、README 和两份 skill，加入 breaking migration 表。
6. 运行聚焦测试、全量 pytest、npm 测试、compileall、mock smoke；在具备凭据时分别记录五类 provider 的真实 smoke 结果。
7. 将版本提升到 `0.3.0-beta.x`，检查 Python/npm 发布资源一致性后提交各阶段 commit。

回滚时按阶段 revert：先恢复旧 parser/config 展示，再恢复 provider registry 与 adapter。不得只恢复旧命令而不恢复其原 provider，否则会产生误导性兼容行为。

## Open Questions

无。Firecrawl Map 的 `location` 首版使用 JSON object，严格限制为官方 `country`/`languages` schema；ZRead `language` 已通过实时 `tools/list` 确认为 `zh|en`。

## Official References

- Exa Search API：<https://docs.exa.ai/reference/search>
- Exa 官方 Python SDK（`find_similar` deprecation）：<https://github.com/exa-labs/exa-py>
- Firecrawl Scrape：<https://docs.firecrawl.dev/api-reference/endpoint/scrape>
- Firecrawl Map OpenAPI：<https://docs.firecrawl.dev/api-reference/endpoint/map.md>
- ZRead MCP：<https://docs.bigmodel.cn/cn/coding-plan/mcp/zread-mcp-server.md>
