## ADDED Requirements

### Requirement: Provider 选择由配置驱动
系统 SHALL 按能力和操作从配置读取 provider 链，并 SHALL NOT 在四类 Agent 搜索命令中公开 `--providers`、`--provider`、`--fallback` 或同类底层选择参数。

#### Scenario: 使用配置顺序
- **WHEN** 某能力配置了多个 provider
- **THEN** 系统按配置的优先顺序尝试 provider
- **AND** Agent 调用命令时无需知道该顺序

#### Scenario: 忽略未配置 provider
- **WHEN** provider 缺少必要凭据或被配置为禁用
- **THEN** 系统不将其作为可执行候选
- **AND** `doctor` 能向维护者报告缺失或禁用状态

### Requirement: 能力与 Provider 对应关系
系统 SHALL 在内部维护 provider 的 `capability.operation` 声明，并只允许 provider 进入其支持的同操作能力链。

#### Scenario: 通用搜索 provider
- **WHEN** 系统构建 `search` 能力链
- **THEN** 回答或综合候选可包括 `xai-responses`、`openai-compatible`
- **AND** 网页来源发现候选可包括 `zhipu`、`zhipu-mcp`、`tavily`、`firecrawl`

#### Scenario: 文档搜索 provider
- **WHEN** 系统构建 `docs.search` 能力链
- **THEN** 候选可包括用于库/API 文档的 `context7`、用于官方页面发现的 `exa`、用于仓库知识搜索的 `zhipu-mcp-zread.search_doc`

#### Scenario: 仓库结构 provider
- **WHEN** 系统构建 `docs.tree` 能力链
- **THEN** 当前候选包括 `zhipu-mcp-zread.get_repo_structure`
- **AND** 不加入只支持文档搜索的 provider

#### Scenario: 仓库文件 provider
- **WHEN** 系统构建 `docs.read` 能力链
- **THEN** 当前候选包括 `zhipu-mcp-zread.read_file`
- **AND** 不加入只支持网页抓取或文档搜索的 provider

#### Scenario: 内容抓取 provider
- **WHEN** 系统构建 `fetch` 能力链
- **THEN** 候选可包括 `jina`、`tavily`、`zhipu-mcp-reader`、`firecrawl`

#### Scenario: 网站探索 provider
- **WHEN** 系统构建 `map` 能力链
- **THEN** 当前候选包括 `tavily`
- **AND** 后续新增站点探索 provider 不改变 Agent 命令契约

#### Scenario: Map 能力边界
- **WHEN** provider 只支持单页结构化提取或仓库目录读取
- **THEN** 系统不将其加入 `map` 能力链
- **AND** `map` 只接收支持通用站点 URL 发现与链接结构遍历的 provider

### Requirement: 自动 Fallback
系统 SHALL 在同一 `capability.operation` 能力链内自动执行 fallback，并根据错误类型决定继续、终止或报告配置问题。

#### Scenario: 可恢复错误触发 fallback
- **WHEN** provider 返回 `timeout`、`network_error`、`rate_limited` 或空结果
- **THEN** 系统尝试支持同一操作的下一个已配置 provider

#### Scenario: 禁止跨操作 fallback
- **WHEN** `docs.tree` 或 `docs.read` 的 provider 失败
- **THEN** 系统不得使用 `docs.search` 结果替代目录结构或文件正文
- **AND** 没有其他同操作 provider 时返回统一失败结果

#### Scenario: Provider 配置错误
- **WHEN** 某个候选返回 `auth_error` 或 provider 局部 `config_error`
- **THEN** 系统记录该候选失败并继续其他已配置候选
- **AND** 在诊断信息中提示维护者修复该 provider 配置

#### Scenario: 请求参数错误
- **WHEN** 请求本身存在 `parameter_error`
- **THEN** 系统停止无意义的 provider fallback
- **AND** 返回统一参数错误

#### Scenario: 所有候选失败
- **WHEN** 能力链中的所有候选均失败
- **THEN** 系统返回该能力的统一失败结果
- **AND** 默认错误摘要不要求 Agent 手工重试某个 provider 专用命令

### Requirement: Provider 结果归一化
系统 SHALL 将不同 provider 的响应转换为统一的内容、来源和错误模型，provider 适配器不得把供应商特有响应结构泄漏给四类 Agent 搜索命令。

#### Scenario: 合并不同来源结构
- **WHEN** provider 使用不同字段表达标题、URL、摘要或正文
- **THEN** 服务层将其归一化为公共输出字段

#### Scenario: 保留诊断溯源
- **WHEN** 开启 debug 或运行诊断命令
- **THEN** 系统可额外返回经过脱敏的 `provider_attempts`、延迟和 fallback 原因
- **AND** 普通 Agent 输出默认省略这些字段

### Requirement: 配置支持能力链管理
配置系统 SHALL 支持为 `search`、`docs.search`、`docs.tree`、`docs.read`、`fetch`、`map` 分别设置 provider 顺序、禁用项、超时和 fallback 开关，并 SHALL 保持凭据与路由策略对 Agent 不可见。

#### Scenario: 调整文档 provider 顺序
- **WHEN** 维护者在配置中将 Exa 调整到 Context7 之前
- **THEN** 后续 `docs search` 调用按新顺序执行
- **AND** Agent skill 和调用参数无需改变

#### Scenario: 禁用单个 provider
- **WHEN** 维护者禁用某个 provider
- **THEN** 所有关联能力链跳过该 provider
- **AND** 其他 provider 继续提供相同公开能力

### Requirement: 移除 AnySearch 与垂直路由
系统 SHALL 删除 AnySearch provider、命令、配置字段、测试契约和 `vertical_search` 路由，并 SHALL NOT 在通用 `search` 中保留 AnySearch fallback。

#### Scenario: 查看新版 provider 配置
- **WHEN** 维护者查看 setup、config 或 doctor 输出
- **THEN** 系统不再展示 AnySearch 配置或垂直搜索能力

#### Scenario: 调用旧 AnySearch 命令
- **WHEN** 用户运行 `anysearch-domains`、`anysearch-search`、`anysearch-extract` 或 `anysearch-batch`
- **THEN** CLI 将其视为不存在的命令
- **AND** 发布迁移文档说明论文和垂直搜索将在后续通过 paper-search 独立扩展
