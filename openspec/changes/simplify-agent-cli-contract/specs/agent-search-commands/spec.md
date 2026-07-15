## ADDED Requirements

### Requirement: Agent 搜索命令面保持最小化
系统 SHALL 在默认帮助和 Agent skill 中只公开 `search`、`docs`、`fetch`、`map` 四个搜索命令，且 SHALL NOT 要求 Agent 选择 provider、模型、fallback 链或路由器。

#### Scenario: 查看默认搜索命令
- **WHEN** 用户运行 `smart-search --help`
- **THEN** 帮助信息将 `search`、`docs`、`fetch`、`map` 列为 Agent 可调用的搜索能力
- **AND** 不将 provider 专用查询命令列为常规搜索入口

#### Scenario: Agent skill 描述工具能力
- **WHEN** Agent 读取随包发布或仓库内的 `smart-search-cli` skill
- **THEN** skill 仅指导 Agent 在四个能力命令之间选择
- **AND** 不指导 Agent 根据 provider 可用性手工选择命令

### Requirement: 通用网页搜索
系统 SHALL 提供 `smart-search search QUERY`，用于搜索开放网页并返回与问题相关的回答或结果及其来源。

#### Scenario: 执行通用网页查询
- **WHEN** Agent 运行 `smart-search search "今天国内有哪些 AI 政策更新"`
- **THEN** 系统使用配置的通用搜索能力链完成查询
- **AND** 返回统一结果而不要求 Agent 指定实际 provider

#### Scenario: 搜索能力不可用
- **WHEN** 没有为通用搜索配置任何可用 provider
- **THEN** 命令返回 `config_error`
- **AND** 错误信息指导维护者运行 `setup` 或 `doctor`，而不是要求 Agent 改用某个 provider 命令

### Requirement: 代码与技术文档操作
系统 SHALL 将 `docs` 作为能力命名空间，并 SHALL 提供 `search`、`tree`、`read` 三个 provider 无关的子命令，分别表达文档/仓库知识搜索、仓库目录结构读取和仓库文件读取。

#### Scenario: 查询库文档
- **WHEN** Agent 运行 `smart-search docs search "React useEffect cleanup 行为"`
- **THEN** 系统自动选择配置的文档查询 provider
- **AND** 返回相关文档片段与可追溯来源

#### Scenario: 搜索代码仓库知识
- **WHEN** Agent 运行 `smart-search docs search "最近的重要 issue 和 PR" --source owner/repo`
- **THEN** 系统将该来源约束传递给支持仓库文档的内部 provider
- **AND** 不要求 Agent 知道具体的仓库文档 provider 名称

#### Scenario: 查看仓库目录结构
- **WHEN** Agent 运行 `smart-search docs tree owner/repo --path src --ref main`
- **THEN** 系统调用支持仓库结构读取的 provider
- **AND** 返回路径、条目类型和层级等规范化目录信息

#### Scenario: 读取仓库文件
- **WHEN** Agent 运行 `smart-search docs read owner/repo README.md --ref main`
- **THEN** 系统调用支持仓库文件读取的 provider
- **AND** 返回指定 revision 下的文件正文和来源信息

#### Scenario: 不使用搜索结果冒充结构或文件
- **WHEN** `docs tree` 或 `docs read` 没有配置支持同操作的 provider
- **THEN** 命令返回明确的 `config_error`
- **AND** 不 fallback 到只支持 `docs search` 的 provider

### Requirement: 已知 URL 内容抓取
系统 SHALL 提供 `smart-search fetch URL`，用于获取已知网页、PDF 或公开文档的主要内容，并将 provider 响应归一化为可供 Agent 使用的正文和元数据。

#### Scenario: 抓取普通网页
- **WHEN** Agent 运行 `smart-search fetch https://example.com/article`
- **THEN** 系统按配置的抓取能力链获取主要内容
- **AND** 返回规范化正文、最终 URL 和必要来源信息

#### Scenario: 抓取 PDF
- **WHEN** URL 指向 PDF 或问题上下文明确要求读取 PDF
- **THEN** 系统可在抓取能力链内部优先选择适合 PDF 的已配置 provider
- **AND** 该选择对 Agent 不可见且无需额外参数

### Requirement: 指定网站结构探索
系统 SHALL 提供 `smart-search map URL`，用于发现指定网站内部的相关页面和链接结构；命令 MAY 接受 provider 无关的探索指令和结果数量限制。

#### Scenario: 探索文档站
- **WHEN** Agent 运行 `smart-search map https://docs.example.com --instructions "查找认证和限流文档"`
- **THEN** 系统返回匹配的站内页面 URL、标题或路径信息
- **AND** Agent 可以将候选 URL 交给 `fetch` 继续读取

#### Scenario: Map provider 未配置
- **WHEN** 没有为站点探索配置可用 provider
- **THEN** 命令返回明确的 `config_error`
- **AND** 不静默改成全网搜索

### Requirement: 统一 Agent 输出契约
四类搜索命令 SHALL 默认提供稳定的 JSON 输出，并 SHALL 使用共同的成功、错误和来源字段；Markdown、纯内容和文件输出 SHALL 作为 provider 无关的通用展示选项提供。

#### Scenario: 成功输出
- **WHEN** 任一搜索命令成功完成
- **THEN** 输出至少包含 `ok`、`capability`、`operation`、`content`、`sources` 和 `elapsed_ms`
- **AND** `sources` 中的条目使用统一的 `title`、`url`、`snippet` 字段

#### Scenario: 仓库结构输出
- **WHEN** `docs tree` 成功完成
- **THEN** 输出在公共 envelope 中通过 `entries` 返回规范化目录条目
- **AND** 每个条目至少标识路径和条目类型

#### Scenario: 失败输出
- **WHEN** 任一搜索命令失败
- **THEN** 输出至少包含 `ok=false`、稳定的 `error_type` 和可执行的 `error`
- **AND** 默认输出不包含密钥、完整配置或内部异常堆栈
