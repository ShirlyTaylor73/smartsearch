## ADDED Requirements

### Requirement: Operation 到 Provider 的固定责任映射
系统 SHALL 使用不可由运行时配置重排的固定责任映射：`search.answer` → Grok，`search.sources|similar` → Exa，`docs.resolve` → Context7，普通 `docs.search` → Context7，仓库 `docs.search` 与 `docs.tree|read` → Zhipu MCP ZRead，`fetch.content|extract` 与 `map.site` → Firecrawl。

#### Scenario: 构建 operation executor
- **WHEN** 服务层解析任一公开 operation
- **THEN** executor 只绑定规格指定的 provider/tool
- **AND** 不生成 provider 候选列表

### Requirement: Grok Transport 必须显式二选一
配置系统 SHALL 要求 `SMART_SEARCH_GROK_TRANSPORT` 为 `xai-responses` 或 `openai-compatible`，并 MUST 只验证和执行被选中的 transport。

#### Scenario: 两组凭据同时存在
- **WHEN** XAI 与 OpenAI-compatible 配置均存在且 transport 选择 `xai-responses`
- **THEN** `search.answer` 只使用 XAI 配置
- **AND** OpenAI-compatible 配置不得成为 fallback

#### Scenario: 选中的 transport 未配置
- **WHEN** transport 选择 `openai-compatible` 但对应 URL、key 或 model 缺失
- **THEN** `search.answer` 返回 `config_error`
- **AND** 不尝试 xAI Responses

### Requirement: 禁止跨 Provider 与跨 Operation Fallback
任一 operation 的唯一 provider 未配置、失败或返回空结果时，系统 SHALL 终止该 operation，并 SHALL NOT 调用其他 provider 或用其他 operation 的结果替代。

#### Scenario: Exa 来源搜索失败
- **WHEN** Exa `search.sources` 请求在有限同 provider 重试后失败
- **THEN** 系统返回统一失败结果
- **AND** 不调用 Firecrawl、Tavily、Zhipu 或 Grok 搜索

#### Scenario: ZRead Tree 失败
- **WHEN** ZRead `get_repo_structure` 失败
- **THEN** `docs.tree` 返回错误
- **AND** 不使用 Context7 docs 或 `search_doc` 冒充目录结构

#### Scenario: Firecrawl Extract 失败
- **WHEN** Firecrawl JSON extraction 失败
- **THEN** `fetch.extract` 返回错误
- **AND** 不以 `fetch.content` 的 Markdown 冒充结构化结果

### Requirement: 同 Provider 重试受统一预算限制
系统 MAY 对可恢复的网络错误执行有限的同 provider 重试，但 MUST 保持相同 operation、endpoint 与等价请求参数，并 MUST 受 operation timeout 预算限制。

#### Scenario: 可恢复网络错误
- **WHEN** 唯一 provider 返回 408、429、可重试 5xx 或瞬时网络错误
- **THEN** adapter 可按配置上限重试同一请求
- **AND** 不切换 provider

#### Scenario: 参数或认证错误
- **WHEN** provider 返回 400、401、403 或 422
- **THEN** 系统不进行 provider fallback
- **AND** 返回对应 `parameter_error` 或 `auth_error`

### Requirement: 删除 Provider 链配置
配置系统 SHALL 删除 provider order、disabled candidate、feature negotiation 与 fallback mode，并 SHALL NOT 接受这些字段改变 operation 责任映射。

#### Scenario: 读取旧 operation 配置
- **WHEN** 旧配置文件包含 `SMART_SEARCH_OPERATION_CONFIG` 的 providers、disabled 或 fallback 字段
- **THEN** 系统不使用这些字段执行路由
- **AND** setup、doctor 或迁移文档提供清理提示

#### Scenario: 配置固定超时
- **WHEN** 维护者为已知 operation 配置 timeout override
- **THEN** 系统只改变该 operation 的总超时预算
- **AND** 不改变其 provider 或参数能力

### Requirement: 最小凭据集合
setup 与 config SHALL 只把 Grok 选定 transport、Exa、Context7、Zhipu MCP ZRead、Firecrawl 作为查询能力凭据，并 SHALL 移除其他 provider 的配置入口。

#### Scenario: 运行 setup
- **WHEN** 维护者运行 `smart-search setup`
- **THEN** 向导要求选择 Grok transport 并配置五类责任 provider 所需凭据
- **AND** 不询问 Tavily、Jina、Zhipu REST、Zhipu MCP Search/Reader 或 DeepWiki

#### Scenario: 查看配置
- **WHEN** 维护者运行 `smart-search config list`
- **THEN** 系统展示保留配置并掩码所有 key/token
- **AND** 不展示已删除 provider 的配置字段

### Requirement: 固定路由错误分类
operation executor SHALL 使用稳定错误类型区分配置、参数、认证、限流、超时、网络、解析和 provider 错误，错误内容 MUST 可执行且不得泄漏敏感信息。

#### Scenario: 缺少唯一 provider 凭据
- **WHEN** operation 对应的唯一 provider key 未配置
- **THEN** 系统返回 `config_error` 并指出缺失配置与 diagnose 命令
- **AND** 不展示其他 provider 建议

#### Scenario: Provider 响应包含密钥
- **WHEN** upstream 错误文本意外包含配置的 key/token
- **THEN** 系统在日志和 CLI 输出前完成脱敏
- **AND** debug 模式也不得输出原值

### Requirement: Diagnose 报告固定责任
`doctor` 与 `diagnose search|docs|fetch|map` SHALL 按 operation 报告固定 responsible provider、配置与连接状态，而 SHALL NOT 报告候选顺序或 fallback 状态。

#### Scenario: 诊断 search sources
- **WHEN** 维护者运行 `smart-search diagnose search sources`
- **THEN** 结果标识 responsible provider 为 Exa 并检查 Exa 配置与连接
- **AND** 不返回 provider candidate 列表

#### Scenario: 诊断仓库 docs
- **WHEN** 维护者运行 `smart-search diagnose docs tree`
- **THEN** 结果检查 ZRead `get_repo_structure` 所需 endpoint、token 与工具 schema
- **AND** 不检查 Context7 fallback

#### Scenario: 运行整体 doctor
- **WHEN** 维护者运行 `smart-search doctor`
- **THEN** 系统逐项报告全部公开 operation 的责任 provider 和可用性
- **AND** 同一 provider 覆盖多个 operation 时仍分别报告 operation executor 状态

### Requirement: Provider Diagnose 仅覆盖保留集合
`diagnose provider` SHALL 只提供 xAI Responses、OpenAI-compatible、Exa、Context7、Zhipu MCP ZRead 和 Firecrawl 的专项检查。

#### Scenario: 检查 Firecrawl
- **WHEN** 维护者运行 Firecrawl provider diagnose
- **THEN** 系统分别验证 Scrape content、JSON extraction 与 Map 所需的配置/schema
- **AND** 结果不声称仅凭 key 存在就已通过真实连接测试

### Requirement: 发布与迁移边界
该确定性 provider 契约 MUST 通过破坏性预发布版本交付，并 MUST 在发布文档中列出删除的 provider、配置键、CLI 参数和替代 operation。

#### Scenario: 构建发布包
- **WHEN** 构建 `0.3.0-beta.x` Python 与 npm 包
- **THEN** 两个包包含相同的新版 CLI help、README 摘要和 Agent skill
- **AND** 不包含已删除 provider 的公开入口或过期 skill 指令
