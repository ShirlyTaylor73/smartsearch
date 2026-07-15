## ADDED Requirements

### Requirement: Provider 选择由 Operation 配置驱动
系统 SHALL 按 `capability.operation` 从配置读取 provider 链，并 SHALL NOT 在四大 Agent 查询命名空间中公开 provider 或 fallback 选择参数。

#### Scenario: 使用配置顺序
- **WHEN** 某 operation 配置了多个 provider
- **THEN** 系统按配置优先顺序尝试候选
- **AND** Agent 调用参数无需包含 provider 名称

#### Scenario: 忽略不可执行候选
- **WHEN** provider 缺少凭据、被禁用或未声明目标 operation
- **THEN** 系统不将其加入候选链
- **AND** doctor/diagnose 向维护者报告原因

### Requirement: Operation 与 Provider 映射
系统 SHALL 在 provider profile 中维护精确 operation 声明，并只允许 provider 进入其支持的 operation 链。

#### Scenario: Search operations
- **WHEN** 系统构建 search operation 链
- **THEN** `search.answer` 可包括 `xai-responses`、`openai-compatible`
- **AND** `search.sources` 可包括 `exa`、`zhipu`、`zhipu-mcp`、`tavily`、`firecrawl`
- **AND** `search.similar` 当前可包括 `exa`

#### Scenario: Docs operations
- **WHEN** 系统构建 docs operation 链
- **THEN** `docs.resolve` 当前可包括 `context7`
- **AND** `docs.search` 可包括 `context7`、`exa`、`zhipu-mcp-zread.search_doc`
- **AND** `docs.tree` 当前可包括 `zhipu-mcp-zread.get_repo_structure`
- **AND** `docs.read` 当前可包括 `zhipu-mcp-zread.read_file`

#### Scenario: Fetch operations
- **WHEN** 系统构建 fetch operation 链
- **THEN** `fetch.content` 可包括 `tavily`、`jina`、`zhipu-mcp-reader`、`firecrawl`
- **AND** `fetch.extract` 只包括实现结构化输出的 `firecrawl` 或未来同类 provider

#### Scenario: Map operation
- **WHEN** 系统构建 `map.site` 链
- **THEN** 当前候选包括 `tavily`
- **AND** 不包括 `docs.tree` 或 `fetch.content` provider operation

### Requirement: Provider Feature Negotiation
系统 SHALL 允许 provider profile 为 operation 声明支持的过滤与输出 feature，并 SHALL 在执行前按调用要求筛选候选。

#### Scenario: Search sources feature 匹配
- **WHEN** 调用要求 semantic mode、domain filter、category、text 或 highlights
- **THEN** executor 只保留支持所有必需 feature 的 `search.sources` provider

#### Scenario: 没有 feature 匹配候选
- **WHEN** 没有已配置 provider 支持全部必需 feature
- **THEN** 系统返回 `capability_error`
- **AND** 错误说明缺失的 feature，而不是静默忽略参数

### Requirement: 同 Operation Fallback
系统 SHALL 只在相同 `capability.operation` 内执行 fallback，并根据错误类型决定继续或终止。

#### Scenario: 可恢复错误
- **WHEN** provider 返回 `timeout`、`network_error`、`rate_limited` 或空结果
- **THEN** 系统尝试相同 operation 的下一个候选

#### Scenario: 禁止跨 operation fallback
- **WHEN** `docs.tree`、`docs.read` 或 `fetch.extract` 的候选失败
- **THEN** 系统不得使用 `docs.search`、`fetch.content` 或其他 operation 结果替代

#### Scenario: 参数错误
- **WHEN** 请求存在 `parameter_error`
- **THEN** 系统停止 provider fallback 并返回统一参数错误

#### Scenario: 所有候选失败
- **WHEN** operation 链中所有候选失败
- **THEN** 系统返回该 operation 的统一失败结果
- **AND** 默认错误不要求 Agent 手工调用 provider 专用命令

### Requirement: Provider 结果归一化
系统 SHALL 将 provider 响应转换为公共 envelope 和 operation 特有字段，不得泄漏供应商特有响应结构。

#### Scenario: 来源结果归一化
- **WHEN** search/docs provider 使用不同字段表示标题、URL、摘要或正文
- **THEN** 服务层将其归一化为公共 source/result 字段

#### Scenario: 结构化 evidence 归一化
- **WHEN** `fetch.extract` provider 返回结构化字段和原始证据
- **THEN** 服务层分别映射为 `data` 和 `raw_evidence`

#### Scenario: 诊断溯源
- **WHEN** 开启 debug 或运行 diagnose
- **THEN** 系统可附加脱敏 `provider_attempts`、feature 匹配、延迟和 fallback 原因
- **AND** 普通 Agent 输出默认省略这些元数据

### Requirement: 配置支持完整 Operation 链
配置系统 SHALL 支持为 `search.answer`、`search.sources`、`search.similar`、`docs.resolve`、`docs.search`、`docs.tree`、`docs.read`、`fetch.content`、`fetch.extract`、`map.site` 分别设置 provider 顺序、禁用项、超时和 fallback。

#### Scenario: 调整 operation 顺序
- **WHEN** 维护者调整 `search.sources` 或 `docs.search` 的 provider 顺序
- **THEN** 后续调用按新顺序执行
- **AND** Agent skill 和命令参数不变

#### Scenario: 单点 operation
- **WHEN** 某 operation 只有一个已配置 provider
- **THEN** 系统仍允许调用
- **AND** doctor/diagnose 标识其没有同 operation fallback

### Requirement: 移除 AnySearch 与垂直路由
系统 SHALL 删除 AnySearch provider、命令、配置、测试契约和 `vertical_search` 路由，并 SHALL NOT 提供 `search.vertical`、`search.domains` 或 `search.batch`。

#### Scenario: 查看新版配置和帮助
- **WHEN** 维护者查看 setup、config、doctor 或 help
- **THEN** 系统不展示 AnySearch 或上述垂直 operation

#### Scenario: 调用旧 AnySearch 命令
- **WHEN** 用户运行任一旧 AnySearch 命令
- **THEN** CLI 将其视为不存在的命令
- **AND** 迁移文档说明后续由 paper-search change 扩展论文和垂直搜索
