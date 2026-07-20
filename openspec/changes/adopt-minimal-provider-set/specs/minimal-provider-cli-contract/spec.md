## ADDED Requirements

### Requirement: 固定的四大能力命令树
系统 SHALL 公开 `search answer|sources|similar`、`docs resolve|search|tree|read`、`fetch content|extract` 和 `map site`，并 SHALL NOT 在这些 Agent 查询命令中接受 provider 或 fallback 选择参数。

#### Scenario: 查看查询帮助
- **WHEN** 用户运行 `smart-search --help` 或任一四大能力的 `--help`
- **THEN** 帮助展示任务子命令及其公开参数
- **AND** 不把 provider 专用旧命令列为查询入口

### Requirement: Search Answer 固定使用 Grok
`smart-search search answer QUERY` SHALL 只使用配置选择的 Grok transport 生成网络回答，并 SHALL 返回可追溯来源。

#### Scenario: 使用 xAI Responses transport
- **WHEN** `SMART_SEARCH_GROK_TRANSPORT=xai-responses` 且对应配置完整
- **THEN** `search answer` 只调用 xAI Responses API
- **AND** 不调用 OpenAI-compatible endpoint

#### Scenario: 使用 OpenAI-compatible transport
- **WHEN** `SMART_SEARCH_GROK_TRANSPORT=openai-compatible` 且对应配置完整
- **THEN** `search answer` 只调用 OpenAI-compatible Chat Completions API
- **AND** stream 行为由配置决定而不是由 Agent 参数选择

### Requirement: Search Sources 固定使用 Exa Search
`smart-search search sources QUERY` SHALL 只调用 Exa Search，并 SHALL 支持 `--limit`、`--mode semantic|keyword|auto`、`--start-published-date`、`--include-domains`、`--exclude-domains`、`--category`、`--include-text` 和 `--include-highlights`。

#### Scenario: 执行语义来源搜索
- **WHEN** Agent 运行 `smart-search search sources "agent search" --mode semantic --limit 5 --include-highlights`
- **THEN** 系统把 `semantic` 映射为 Exa 的 neural search 并传递结果数量与 highlights 参数
- **AND** 返回规范化 `results` 与 `sources`

#### Scenario: Exa 不接受请求参数
- **WHEN** 请求参数不能合法映射到 Exa Search schema
- **THEN** 系统在调用前或收到 400/422 后返回 `parameter_error`
- **AND** 不尝试其他 search provider

### Requirement: Search Similar 固定使用 Exa Find Similar
`smart-search search similar URL` SHALL 只调用 Exa Find Similar，并 SHALL 支持 `--limit` 控制最大结果数。

#### Scenario: 查找相似页面
- **WHEN** Agent 运行 `smart-search search similar https://example.com/article --limit 3`
- **THEN** 系统调用 Exa `/findSimilar`
- **AND** 返回最多三个规范化相似页面结果

### Requirement: Docs Resolve 固定使用 Context7
`smart-search docs resolve NAME [QUERY]` SHALL 只使用 Context7 library resolve/search 返回候选文档来源标识。

#### Scenario: 解析库名称
- **WHEN** Agent 运行 `smart-search docs resolve nextjs "app router"`
- **THEN** 系统调用 Context7 library resolve/search
- **AND** 通过 `candidates` 返回稳定 id、标题和描述

### Requirement: Docs Search 确定性分流
`smart-search docs search QUERY [--source SOURCE]` SHALL 根据 source 语义确定使用 Context7 或 Zhipu MCP ZRead，且一次调用 MUST 只执行其中一个 provider。

#### Scenario: 搜索普通库或 API 文档
- **WHEN** source 为空或为 Context7 library id
- **THEN** 系统只调用 Context7 docs/context lookup
- **AND** 不调用 ZRead 或 Exa

#### Scenario: 搜索 GitHub 仓库知识
- **WHEN** Agent 运行 `smart-search docs search "最近的重要 PR" --source owner/repo`
- **THEN** 系统只调用 ZRead `search_doc(repo_name, query, language?)`
- **AND** `repo_name` 等于规范化的 `owner/repo`

#### Scenario: Source 形式无效
- **WHEN** source 既不是有效 Context7 library id 也不是规范化 `owner/repo`
- **THEN** 系统返回 `parameter_error`
- **AND** 不发出 provider 请求

### Requirement: Docs Tree 固定使用 ZRead
`smart-search docs tree REPO [--path PATH]` SHALL 只调用 ZRead `get_repo_structure(repo_name, dir_path?)`，并 SHALL NOT 接受 `--ref`。

#### Scenario: 查看子目录结构
- **WHEN** Agent 运行 `smart-search docs tree owner/repo --path src`
- **THEN** 系统把 repo 映射为 `repo_name`、path 映射为 `dir_path`
- **AND** 通过 `entries` 返回规范化目录结果

#### Scenario: 使用已删除的 ref 参数
- **WHEN** 用户运行 `smart-search docs tree owner/repo --ref main`
- **THEN** CLI 返回参数错误
- **AND** 不向 ZRead 发送未声明的 `ref`

### Requirement: Docs Read 固定使用 ZRead
`smart-search docs read REPO PATH` SHALL 只调用 ZRead `read_file(repo_name, file_path)`，并 SHALL NOT 接受 `--ref`。

#### Scenario: 读取仓库文件
- **WHEN** Agent 运行 `smart-search docs read owner/repo README.md`
- **THEN** 系统调用 ZRead `read_file` 并返回文件正文
- **AND** 请求只包含 `repo_name` 与 `file_path`

### Requirement: Fetch Content 固定使用 Firecrawl Scrape
`smart-search fetch content URL` SHALL 只调用 Firecrawl Scrape 获取适合阅读和引用的正文或 Markdown。

#### Scenario: 抓取已知 URL
- **WHEN** Agent 运行 `smart-search fetch content https://example.com/article`
- **THEN** 系统请求 Firecrawl Scrape 的可读内容 format
- **AND** 返回正文、最终 URL 与来源信息

### Requirement: Fetch Extract 固定使用 Firecrawl JSON extraction
`smart-search fetch extract URL` SHALL 只调用 Firecrawl Scrape 的 JSON format，并 SHALL 支持 `--schema` 与 `--max-length`。

#### Scenario: 按 schema 提取结构化数据
- **WHEN** Agent 提供合法 JSON Schema 运行 `fetch extract`
- **THEN** 系统把 schema 传递给 Firecrawl JSON extraction
- **AND** 通过 `data` 返回结构化结果并通过 `raw_evidence` 返回受长度限制的证据

#### Scenario: Schema 无效
- **WHEN** `--schema` 不是 JSON object 或不是有效 schema
- **THEN** 系统返回 `parameter_error`
- **AND** 不退化为普通 Markdown 抓取

### Requirement: Map Site 固定使用 Firecrawl Map
`smart-search map site URL` SHALL 只调用 Firecrawl Map，并 SHALL 支持 `--search`、`--sitemap include|skip|only`、`--include-subdomains`、`--ignore-query-parameters`、`--ignore-cache`、`--limit`、`--timeout` 和 `--location`。

#### Scenario: 探索文档站
- **WHEN** Agent 运行 `smart-search map site https://docs.example.com --search authentication --include-subdomains --limit 50`
- **THEN** 系统把参数映射到 Firecrawl Map
- **AND** 通过 `entries` 或 `results` 返回站内 URL

#### Scenario: Tavily Map 参数已移除
- **WHEN** 用户传入 `--instructions`、`--max-depth` 或 `--max-breadth`
- **THEN** CLI 返回参数错误并展示 Firecrawl Map 替代参数
- **AND** 不静默忽略旧参数

### Requirement: 统一输出保持 provider 无关
全部查询 operation SHALL 返回共同 envelope，并 SHALL 将 provider 特有响应规范化为稳定字段。

#### Scenario: 查询成功
- **WHEN** 任一 operation 成功
- **THEN** JSON 至少包含 `ok`、`capability`、`operation`、`content`、`sources` 和 `elapsed_ms`
- **AND** operation 数据使用 `results`、`candidates`、`entries`、`data` 或 `raw_evidence`

#### Scenario: 默认输出隐藏内部细节
- **WHEN** Agent 未启用 `--debug`
- **THEN** 输出不包含 provider 候选、fallback attempts、密钥或内部异常堆栈

### Requirement: 删除不再支持的 provider 兼容入口
CLI SHALL 移除 Tavily、Jina、Zhipu REST、Zhipu MCP Search/Reader、DeepWiki 及旧 provider 专用查询命令，并 SHALL NOT 将旧命令转发给不同 provider。

#### Scenario: 调用旧 provider 命令
- **WHEN** 用户运行已移除的 provider 专用命令
- **THEN** CLI 将其视为不存在的命令
- **AND** 迁移文档指向职责等价的新 operation（如果存在）

### Requirement: 保留功能性命令
系统 SHALL 保留 `setup`、`doctor`、`config path|list|set|unset`、`skills status|update`、`diagnose` 完整命令树、`dev regression`、`-h/--help` 和 `-v/--version`。

#### Scenario: 查看根帮助与版本
- **WHEN** 用户运行 `smart-search -h` 或 `smart-search -v`
- **THEN** CLI 分别输出新版命令概览或 `smart-search <version>`
- **AND** 成功退出
