## ADDED Requirements

### Requirement: 四大 Agent 查询能力
系统 SHALL 在默认帮助和 Agent skill 中只公开 `search`、`docs`、`fetch`、`map` 四大查询命名空间及其任务子命令，并 SHALL NOT 要求 Agent 选择 provider、模型、fallback 链或路由器。

#### Scenario: 查看默认查询能力
- **WHEN** 用户运行 `smart-search --help`
- **THEN** 帮助信息展示四大查询命名空间及其子命令概览
- **AND** 不将 provider 专用命令列为常规查询入口

#### Scenario: Agent skill 描述选择规则
- **WHEN** Agent 读取 `smart-search-cli` skill
- **THEN** skill 根据任务动作指导 Agent 选择 operation
- **AND** 不指导 Agent 根据 provider 可用性选择命令

### Requirement: Search Answer
系统 SHALL 提供 `smart-search search answer QUERY`，用于通过配置的主搜索模型生成问题回答并返回可追溯来源。

#### Scenario: 生成通用网络回答
- **WHEN** Agent 运行 `smart-search search answer "今天国内有哪些 AI 政策更新"`
- **THEN** 系统使用 `search.answer` provider 链完成查询与综合
- **AND** 返回统一回答而不要求 Agent 指定模型 provider

### Requirement: Search Sources
系统 SHALL 提供 `smart-search search sources QUERY`，用于返回来源优先的网页搜索结果；命令 SHALL 支持 provider 无关的 `--limit`、`--mode semantic|keyword|auto`、时间、include/exclude domains、`--category`、`--include-text` 和 `--include-highlights` 参数。

#### Scenario: 执行来源搜索
- **WHEN** Agent 运行 `smart-search search sources "agentic search papers" --limit 5 --mode semantic --include-highlights`
- **THEN** 系统只选择支持 `search.sources` 及所需 feature 的已配置 provider
- **AND** 返回规范化结果列表和来源

#### Scenario: 必需过滤能力不可用
- **WHEN** 已配置 provider 均不支持调用要求的必需过滤 feature
- **THEN** 命令返回明确的 `capability_error`
- **AND** 不静默忽略该过滤条件

### Requirement: Search Similar
系统 SHALL 提供 `smart-search search similar URL`，用于查找与已知 URL 内容相近的页面。

#### Scenario: 查找相似页面
- **WHEN** Agent 运行 `smart-search search similar https://example.com/article`
- **THEN** 系统使用 `search.similar` provider 链
- **AND** 返回规范化相似页面结果

### Requirement: Docs Resolve
系统 SHALL 提供 `smart-search docs resolve NAME [QUERY]`，用于把库或框架名称解析为可供后续文档查询使用的候选来源标识。

#### Scenario: 解析 library
- **WHEN** Agent 运行 `smart-search docs resolve react hooks`
- **THEN** 系统使用 `docs.resolve` provider 链
- **AND** 返回规范化候选标识、标题和描述

### Requirement: Docs Search
系统 SHALL 提供 `smart-search docs search QUERY [--source SOURCE]`，用于查询库/API 文档、官方技术页面或指定代码仓库知识。

#### Scenario: 查询技术文档
- **WHEN** Agent 运行 `smart-search docs search "React useEffect cleanup 行为"`
- **THEN** 系统自动选择配置的 `docs.search` provider
- **AND** 返回文档片段与可追溯来源

#### Scenario: 搜索代码仓库知识
- **WHEN** Agent 运行 `smart-search docs search "最近的重要 issue 和 PR" --source owner/repo`
- **THEN** 系统将中立来源约束传递给支持仓库知识搜索的 provider
- **AND** 不要求 Agent 知道 zread 或其他 provider 名称

### Requirement: Docs Tree
系统 SHALL 提供 `smart-search docs tree REPO [--path PATH] [--ref REF]`，用于读取代码仓库目录结构和文件列表。

#### Scenario: 查看仓库目录
- **WHEN** Agent 运行 `smart-search docs tree owner/repo --path src --ref main`
- **THEN** 系统调用支持 `docs.tree` 的 provider
- **AND** 通过 `entries` 返回规范化路径、条目类型和层级

#### Scenario: Tree operation 不可用
- **WHEN** 没有配置支持 `docs.tree` 的 provider
- **THEN** 命令返回明确的 `config_error`
- **AND** 不使用 `docs.search` 结果冒充目录结构

### Requirement: Docs Read
系统 SHALL 提供 `smart-search docs read REPO PATH [--ref REF]`，用于读取代码仓库中的指定文件。

#### Scenario: 读取仓库文件
- **WHEN** Agent 运行 `smart-search docs read owner/repo README.md --ref main`
- **THEN** 系统调用支持 `docs.read` 的 provider
- **AND** 返回指定 revision 下的文件正文与来源信息

### Requirement: Fetch Content
系统 SHALL 提供 `smart-search fetch content URL`，用于获取适合阅读、总结和引用的网页、PDF 或公开文档正文。

#### Scenario: 抓取网页正文
- **WHEN** Agent 运行 `smart-search fetch content https://example.com/article`
- **THEN** 系统按 `fetch.content` provider 链获取内容
- **AND** 返回规范化正文、最终 URL 和来源信息

#### Scenario: 抓取 PDF
- **WHEN** URL 指向 PDF
- **THEN** 系统可在 `fetch.content` 内部优先选择适合 PDF 的已配置 provider
- **AND** 该选择对 Agent 不可见

### Requirement: Fetch Extract
系统 SHALL 提供 `smart-search fetch extract URL`，用于返回结构化字段或保留原始 evidence；命令 SHALL 接受可选的 `--max-length` 及 provider 无关的结构化 schema 参数。

#### Scenario: 结构化提取成功
- **WHEN** Agent 对已知 URL 运行 `smart-search fetch extract URL`
- **THEN** 系统只选择声明 `fetch.extract` 的 provider
- **AND** 通过 `data` 返回结构化结果，并可通过 `raw_evidence` 保留原始证据

#### Scenario: 没有结构化 provider
- **WHEN** 没有配置支持 `fetch.extract` 的 provider
- **THEN** 命令返回明确的 `config_error`
- **AND** 不把普通 Markdown 正文冒充结构化结果

### Requirement: Map Site
系统 SHALL 提供 `smart-search map site URL`，用于发现指定网站内部的页面 URL、路径和链接结构，并 SHALL 支持 `--instructions`、`--max-depth`、`--max-breadth`、`--limit` 和 `--timeout`。

#### Scenario: 探索文档站
- **WHEN** Agent 运行 `smart-search map site https://docs.example.com --instructions "查找认证页面" --limit 50`
- **THEN** 系统使用 `map.site` provider 链返回匹配的站内页面
- **AND** Agent 可以将候选 URL 交给 `fetch content`

#### Scenario: Map 能力边界
- **WHEN** provider 只支持单页提取或代码仓库目录读取
- **THEN** 系统不将其加入 `map.site`

### Requirement: 统一 Agent 输出契约
四大能力的所有 operation SHALL 默认提供稳定 JSON 输出，并 SHALL 使用共同的成功、错误和来源字段；Markdown、content 和文件输出 SHALL 作为 provider 无关的通用展示选项提供。

#### Scenario: 成功输出
- **WHEN** 任一 operation 成功完成
- **THEN** 输出至少包含 `ok`、`capability`、`operation`、`content`、`sources` 和 `elapsed_ms`
- **AND** operation 特有结果使用规格定义的 `results`、`candidates`、`entries` 或 `data` 字段

#### Scenario: 失败输出
- **WHEN** 任一 operation 失败
- **THEN** 输出至少包含 `ok=false`、稳定的 `error_type` 和可执行的 `error`
- **AND** 默认输出不包含密钥、完整配置或内部异常堆栈
