## Context

当前 `smart-search` 同时暴露任务命令、provider 命令、路由诊断、Deep Research、配置管理和开发回归入口。底层多 provider 有助于覆盖率和容错，但公开命令缺乏稳定的任务抽象；另一方面，若只保留四个无子命令的粗粒度入口，又会丢失相似页面、library resolve、仓库树、文件读取和结构化抽取等有效操作。

本变更采用“四大能力 + operation”的中间层：Agent 选择真实任务操作，配置选择 provider。现有 JSON/Markdown/content 输出属于用户可见契约；provider 凭据、完整配置、内部异常和个人路径不得泄漏。

## Goals / Non-Goals

**Goals:**

- 用四大能力命名空间无损承载除 AnySearch 和 Deep Research 外的现有有效能力。
- 让 Agent 表达 `answer`、`sources`、`similar`、`resolve`、`tree`、`read`、`content`、`extract`、`site` 等任务操作，而不表达 provider。
- 按 `capability.operation` 配置 provider、feature、顺序、超时与 fallback。
- 把路由、provider 专项、smoke 和 regression 收入清晰的维护/开发命令树。
- 保持统一、简洁的 Agent 输出，并提供脱敏 debug/diagnose 溯源。

**Non-Goals:**

- 不保留 AnySearch、通用垂直搜索、domains 或 batch search；论文与垂直能力后续由 paper-search change 扩展。
- 不保留 `deep`、`research` 或在 CLI 内构建第二个研究 Agent。
- 不改变第三方 API 的认证机制，也不要求为每个 operation 都有多个 provider。
- 不把 provider 名称重新包装成普通查询参数。

## Decisions

### 1. 四大能力使用稳定子命令

公开查询结构为：

```text
search
├─ answer QUERY
├─ sources QUERY
└─ similar URL

docs
├─ resolve NAME [QUERY]
├─ search QUERY [--source SOURCE]
├─ tree REPO [--path PATH] [--ref REF]
└─ read REPO PATH [--ref REF]

fetch
├─ content URL
└─ extract URL

map
└─ site URL
```

operation 是 Agent 必须表达的任务语义，不是 provider 细节。`map site` 专指站内 URL、路径和链接结构发现；`docs tree` 专指代码仓库目录；`fetch extract` 专指结构化字段或原始 evidence 提取，三者不得混用。

### 2. 现有能力按 operation 无损映射

| Operation | 内部 provider/tool 候选 |
|---|---|
| `search.answer` | xAI Responses、OpenAI-compatible |
| `search.sources` | Exa Search、Zhipu Web Search、Zhipu MCP `web_search_prime`、Tavily Search、Firecrawl Search |
| `search.similar` | Exa Similar |
| `docs.resolve` | Context7 library |
| `docs.search` | Context7 docs、Exa Search、Zhipu MCP zread `search_doc` |
| `docs.tree` | Zhipu MCP zread `get_repo_structure` |
| `docs.read` | Zhipu MCP zread `read_file` |
| `fetch.content` | Tavily Extract、Jina Reader、Zhipu MCP `webReader`、Firecrawl Scrape |
| `fetch.extract` | Firecrawl 结构化抽取及未来声明同 operation 的 provider |
| `map.site` | Tavily Map |

AnySearch 不出现在映射中。删除 AnySearch 后，`fetch.extract` 仍保留为稳定任务契约，但只有真正实现结构化输出的 provider 才能进入；首期应扩展 Firecrawl 适配器承接该 operation，若未配置则明确返回 `config_error`，不得退化为普通 Markdown。

### 3. 来源搜索参数使用 feature negotiation

`search sources` 保留跨 provider 的任务级参数：

- `--limit`
- `--mode semantic|keyword|auto`
- 发布时间/时间范围
- include/exclude domains
- `--category`
- `--include-text`
- `--include-highlights`

provider profile 除 operations 外还声明 features。executor 先根据 operation 筛选，再根据调用要求筛选 feature；不支持必需参数的 provider 不进入候选链。若没有候选，返回明确的 `capability_error`，不得静默忽略过滤条件。非必需、仅用于改善排序的 hint 可以在统一结果中标记为未应用。

### 4. 配置与 fallback 精确到 operation

配置逻辑结构示例：

```yaml
providers:
  context7:
    operations: [docs.resolve, docs.search]
  zhipu-mcp-zread:
    operations: [docs.search, docs.tree, docs.read]
  exa:
    operations: [search.sources, search.similar, docs.search]
  firecrawl:
    operations: [search.sources, fetch.content, fetch.extract]
```

每个 operation 独立配置优先顺序、禁用项、超时和 fallback。fallback 只能在相同 operation 内发生，例如 `docs.tree` 不得 fallback 到 Context7，`fetch.extract` 不得用 `fetch.content` 的 Markdown 冒充结构化结果。

### 5. 统一公共输出

公共 envelope 包含：`ok`、`capability`、`operation`、`content`、`sources`、`elapsed_ms`；失败增加 `error_type` 和 `error`。operation 特有数据使用稳定字段：

- `search.sources` / `search.similar`：`results`
- `docs.resolve`：`candidates`
- `docs.tree`：`entries`
- `docs.read` / `fetch.content`：`content`
- `fetch.extract`：`data` 与可选 `raw_evidence`
- `map.site`：`entries` 或 `results`

普通输出省略 provider attempts、模型 fallback、breaker、路由评分和堆栈；`--debug`、`doctor`、`diagnose` 和日志可提供脱敏元数据。

### 6. 完整维护与诊断树

```text
diagnose
├─ search [answer|sources|similar]
├─ docs [resolve|search|tree|read]
├─ fetch [content|extract]
├─ map [site]
├─ provider openai-compatible
├─ route QUERY
├─ route-calibrate [--models MODELS]
└─ smoke [--mode mock|live]

dev
└─ regression
```

未指定 operation 时，capability diagnose 依次检查该命名空间全部 operation。原有 `diagnose openai-compatible`、`route`、`route-calibrate`、`smoke` 和 `regression` 分别迁入上述位置。`setup`、`doctor`、`config path|list|set|unset`、`skills status|update`、`-h/--help`、`-v/--version` 保持独立功能入口。

### 7. 删除 AnySearch 与 Deep Research

AnySearch provider、四个 AnySearch 命令、配置项、`vertical_search` 路由及测试契约直接删除，不做兼容转发。`deep`、`research`、计划构建、live executor、evidence artifact 和 research provider override 同样直接删除。相似页面、结构化抽取等非 AnySearch 专属任务能力通过新的 operation 继续保留。

### 8. 旧命令分阶段迁移

有同等 operation 的旧命令在一个发布周期内隐藏兼容，例如 `exa-search` → `search sources`、`exa-similar` → `search similar`、`context7-library` → `docs resolve`、zread 命令 → 对应 docs operation、`fetch` → `fetch content`、`map` → `map site`。AnySearch、`deep`、`research` 不进入兼容层。

## Risks / Trade-offs

- [子命令增多仍可能增加选择成本] → 子命令全部对应互斥、可解释的任务动作；Agent skill 提供简短决策表，不展示 provider。
- [feature negotiation 可能导致候选为空] → 返回明确缺失 feature 和配置建议，不静默降低查询约束。
- [`fetch.extract` 删除 AnySearch 后需要新适配] → 以 Firecrawl 结构化能力承接；未实现或未配置时明确不可用，不伪装成功。
- [部分 operation 只有一个 provider] → doctor/diagnose 标记单点能力，同操作链耗尽时直接失败。
- [迁移层增加短期维护成本] → 只做薄转发与弃用提示，一个发布周期后删除。
- [移除 Deep Research 影响现有人类用户] → README 给出由四大能力组合研究的迁移示例，未来如需研究产品另行设计。

## Migration Plan

1. 先添加完整命令树、operation mapping、feature negotiation、AnySearch/Research 删除行为的失败测试。
2. 删除 AnySearch 与 Deep Research 代码、配置、测试和资源引用。
3. 建立 operation executor 与统一输出，逐一迁移 search/docs/fetch/map 子命令。
4. 扩展 Firecrawl 适配器支持 `fetch.extract` 的结构化输出。
5. 重组 diagnose/dev/配置/帮助命令，加入 operation 级健康检查。
6. 添加旧命令薄兼容层并同步 README 与两份 skill。
7. 完成全量 Python/npm/发布资源验证后按阶段提交。

回滚时可恢复旧 parser 可见性和直接 service 调用；operation executor 与 provider adapter 可继续复用。AnySearch 与 Deep Research 的删除应通过 revert 对应独立阶段 commit 回滚，不与其他 CLI 重构混合。

## Open Questions

- Firecrawl `fetch.extract` 首版的结构化 schema 参数形式需要在实现阶段依据当前官方 API 与仓库版本确定，但公共命令和 `data/raw_evidence` 输出契约保持 provider 无关。
- `search sources` 的时间过滤统一命名需要在实现前对照 Exa、Zhipu、Tavily 和 Firecrawl 当前参数，选择不会暗示某一 provider 的公共字段。
