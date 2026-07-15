## 1. 契约基线与失败测试

- [x] 1.1 重新核对 proposal、design 和三份 spec，记录现有 CLI、service、配置、README、skill 和测试的能力映射基线
- [x] 1.2 在 `tests/` 先添加失败测试，约束四大命名空间及完整 operation：`search answer|sources|similar`、`docs resolve|search|tree|read`、`fetch content|extract`、`map site`
- [x] 1.3 添加统一 envelope、operation 特有字段、默认隐藏 provider metadata 和跨平台输出测试
- [x] 1.4 添加 operation feature negotiation、同 operation fallback 和禁止跨 operation 替代的失败测试
- [x] 1.5 添加完整 diagnose/dev 命令树与旧命令迁移测试
- [x] 1.6 添加 AnySearch/vertical 与 Deep Research 命令、配置、service 路径不存在的失败测试
- [x] 1.7 提交“新版 CLI operation 契约测试”阶段 commit

## 2. 移除 AnySearch 与 Deep Research

- [x] 2.1 删除 AnySearch provider、CLI 命令、service 封装、配置字段、setup 选项和导出引用
- [x] 2.2 删除 `vertical_search` 意图、能力状态、fallback、profile、smoke case 和相关测试契约
- [x] 2.3 删除 `deep`、`research` parser、计划构建、live executor、evidence artifact、research override 和相关 helper
- [x] 2.4 删除或改写 AnySearch/Deep Research 的 pytest、回归断言、README、skill 与打包资源引用
- [x] 2.5 运行聚焦测试确认被移除入口无法解析，其他 operation 不依赖被删除代码
- [x] 2.6 提交“移除 AnySearch 与 Deep Research”阶段 commit

## 3. Operation Profile、配置与 Executor

- [x] 3.1 为 provider profile 增加精确 operations 与 features 声明，覆盖全部保留 provider/tool
- [x] 3.2 在配置层增加十个公开 operation 的顺序、禁用项、超时和 fallback 设置，并保持现有凭据兼容
- [x] 3.3 实现按 `capability.operation` 构建候选链的统一 executor，过滤未配置、禁用和 operation 不匹配的 provider
- [x] 3.4 实现 feature negotiation，区分必需 constraint 与可选 hint，并在候选为空时返回 `capability_error`
- [x] 3.5 实现统一错误分类、同 operation fallback 和总超时预算
- [x] 3.6 添加顺序、禁用、单点 operation、feature 匹配、fallback off、全部失败和禁止跨 operation fallback 的聚焦测试
- [x] 3.7 提交“配置化 operation executor”阶段 commit

## 4. Search 命名空间

- [x] 4.1 实现 `search answer QUERY`，迁移当前主模型搜索、stream、模型 fallback 和来源提取逻辑
- [x] 4.2 实现 `search sources QUERY`，统一 Exa、Zhipu REST、Zhipu MCP、Tavily 和 Firecrawl 来源结果
- [x] 4.3 为 `search sources` 实现 `--limit`、`--mode`、时间、域名、category、正文和 highlights 公共参数及 feature mapping
- [x] 4.4 实现 `search similar URL`，迁移 Exa Similar 并使用统一 results 输出
- [x] 4.5 移除 Agent-facing `--providers`、`--fallback`、router/validation 等底层控制参数
- [x] 4.6 添加 search 三个 operation 的 JSON/Markdown/content/output、错误和 fallback 测试
- [x] 4.7 提交“search operation 命名空间”阶段 commit

## 5. Docs 命名空间

- [x] 5.1 实现 `docs resolve NAME [QUERY]`，迁移 Context7 library 并归一化 candidates
- [x] 5.2 实现 `docs search QUERY [--source SOURCE]`，统一 Context7 docs、Exa 和 Zhipu MCP `search_doc`
- [x] 5.3 实现 `docs tree REPO [--path PATH] [--ref REF]`，迁移 `get_repo_structure` 并归一化 entries
- [x] 5.4 实现 `docs read REPO PATH [--ref REF]`，迁移 `read_file` 并归一化正文和来源
- [x] 5.5 添加 library、普通技术文档、仓库知识、目录和文件读取的聚焦测试
- [x] 5.6 验证 tree/read 没有同 operation provider 时明确失败，不 fallback 到 docs search
- [x] 5.7 提交“docs operation 命名空间”阶段 commit

## 6. Fetch 与 Map 命名空间

- [x] 6.1 实现 `fetch content URL`，统一 Tavily Extract、Jina Reader、Zhipu MCP webReader 和 Firecrawl Scrape
- [x] 6.2 扩展 Firecrawl provider 支持 `fetch extract URL` 的结构化 schema/data/raw_evidence 输出，并保留 provider 无关的 `--max-length`
- [x] 6.3 验证没有 `fetch.extract` provider 时返回明确配置错误，不退化为普通 Markdown
- [x] 6.4 实现 `map site URL`，迁移 Tavily Map 全部 instructions/depth/breadth/limit/timeout 参数
- [x] 6.5 添加网页、PDF、动态页面、结构化抽取和站点结构边界测试
- [x] 6.6 提交“fetch 与 map operation 命名空间”阶段 commit

## 7. 帮助、配置、诊断与开发命令

- [x] 7.1 重组根帮助和各级子命令帮助，分组展示四大查询能力、维护功能和开发功能，并验证 `-h/--help`、`-v/--version`
- [x] 7.2 更新 `setup` 与 `config path|list|set|unset`，支持 operation/feature 配置并确保敏感值默认脱敏
- [x] 7.3 重构 `doctor`，逐 operation 报告配置、连接、feature、fallback 和单点状态
- [x] 7.4 实现 `diagnose search/docs/fetch/map [OPERATION]`，未指定 operation 时检查该 capability 全部 operation
- [x] 7.5 迁移 OpenAI-compatible 专项为 `diagnose provider openai-compatible`
- [x] 7.6 迁移 `route`、`route-calibrate`、`smoke` 为对应 diagnose 子命令
- [x] 7.7 迁移 `regression` 为 `dev regression`，保留 `skills status|update`
- [x] 7.8 实现普通输出与 `--debug` metadata 隔离，并验证日志不污染 stdout JSON
- [x] 7.9 提交“CLI 维护、诊断与开发命令树”阶段 commit

## 8. 兼容迁移、文档与发布验证

- [x] 8.1 为有同等 operation 的旧 search/docs/fetch/map provider 命令实现默认帮助隐藏的薄兼容入口和弃用提示
- [x] 8.2 为旧 diagnose/route/route-calibrate/smoke/regression/model 命令提供新位置迁移提示
- [x] 8.3 确认 AnySearch、deep、research 不进入兼容层且不再出现在 Agent skill
- [x] 8.4 更新 `README.zh-CN.md` 和 `README.md`，完整说明命令树、参数、provider operation 映射、fallback 和迁移表
- [x] 8.5 明确 `map site`、`docs tree`、`fetch content`、`fetch extract` 的边界，并说明 paper-search 后续扩展计划
- [x] 8.6 同步更新 `skills/smart-search-cli/` 与打包副本，只教授四大能力及其 operation，并验证两份资源一致
- [x] 8.7 重新检查 OpenSpec、最终实现、测试和用户文档的一致性
- [x] 8.8 运行 `python -m compileall -q src tests`、聚焦 pytest、完整 `python -m pytest tests -q`、`npm test` 和 `git diff --check`
- [x] 8.9 检查最终 diff、status、敏感信息和跨平台兼容，并提交发布准备阶段 commit
