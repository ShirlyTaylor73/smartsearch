## 1. 契约固化与失败测试

- [ ] 1.1 重新核对 proposal、design 和三份 capability spec，记录现有 CLI、配置、service、README 与 skill 的影响基线
- [ ] 1.2 在 `tests/` 先添加失败测试，约束默认帮助只公开 `search`、`docs`、`fetch`、`map` 四类能力，并验证 `docs search|tree|read` 子命令
- [ ] 1.3 添加统一成功/失败 envelope、`operation` 字段、来源字段、`docs tree` entries 和默认隐藏 provider metadata 的契约测试
- [ ] 1.4 添加 AnySearch 命令/配置/路由不存在以及 `deep`、`research` 命令和实现被移除的失败测试
- [ ] 1.5 添加其他旧 provider 命令隐藏、弃用提示和一个发布周期兼容行为的测试
- [ ] 1.6 提交“新版 CLI 契约测试”阶段 commit

## 2. 移除 AnySearch 与 Deep Research

- [ ] 2.1 删除 AnySearch provider、CLI 命令、service 封装、配置字段、setup 选项和导出引用
- [ ] 2.2 删除 `vertical_search` 意图、能力状态、fallback、provider profile、smoke case 和相关测试契约
- [ ] 2.3 删除 `deep`、`research` parser、计划构建、live research、evidence artifact、research provider override 和相关 service helper
- [ ] 2.4 删除或改写 AnySearch/Deep Research 的 pytest、回归断言、README、skill 和打包资源引用
- [ ] 2.5 运行聚焦测试确认被移除命令无法解析且普通 `search/docs/fetch/map` 不依赖被删除代码
- [ ] 2.6 提交“移除 AnySearch 与 Deep Research”阶段 commit

## 3. 配置化能力与操作链

- [ ] 3.1 在配置层增加 `search`、`docs.search`、`docs.tree`、`docs.read`、`fetch`、`map` 的 provider 顺序、禁用项、超时和 fallback 设置
- [ ] 3.2 为 provider profile 补齐 `capability.operation` 声明：Context7/Exa/zread 文档操作、Jina/Tavily/Zhipu Reader/Firecrawl 抓取及 Tavily map
- [ ] 3.3 实现按能力和操作构建候选链的统一 helper，过滤未配置、禁用和操作不匹配的 provider
- [ ] 3.4 实现同操作 fallback 与统一错误分类，覆盖 timeout、network、rate limit、empty、auth/config 和 parameter error
- [ ] 3.5 添加能力链顺序、禁用、fallback off、总超时、全部失败和禁止跨操作 fallback 的聚焦测试
- [ ] 3.6 提交“配置化 capability operation 路由”阶段 commit

## 4. 四类 Agent 搜索能力

- [ ] 4.1 定义公共结果数据结构和 provider 响应归一化 helper，统一 `ok`、`capability`、`operation`、`content`、`sources`、`elapsed_ms` 与错误字段
- [ ] 4.2 将 `search` 重构为配置驱动的回答与网页来源发现流程，移除 Agent-facing `--providers`、`--fallback` 和 router/validation 控制
- [ ] 4.3 实现 `docs search QUERY [--source SOURCE]`，统一 Context7、Exa 和 Zhipu MCP `search_doc` 的搜索结果
- [ ] 4.4 实现 `docs tree SOURCE [--path PATH] [--ref REF]`，通过同操作 provider 返回规范化目录 entries
- [ ] 4.5 实现 `docs read SOURCE PATH [--ref REF]`，通过同操作 provider 返回文件正文和来源信息
- [ ] 4.6 将 `fetch URL` 接入统一 executor，并保留网页、PDF、动态页面的内部 provider 优先策略
- [ ] 4.7 将 `map URL` 接入统一 executor，明确只做站内 URL/链接结构探索并保留 provider 无关的 instructions、limit 参数
- [ ] 4.8 为四类能力添加 JSON、Markdown、content、output 文件和跨平台编码测试
- [ ] 4.9 提交“四类 Agent 搜索能力”阶段 commit

## 5. 帮助、配置和错误排查

- [ ] 5.1 重组根帮助和子命令帮助，明确四类 Agent 搜索能力、`docs` 子操作与维护者功能，并验证 `-h/--help`、`-v/--version`
- [ ] 5.2 更新 `setup` 和 `config path|list|set|unset`，支持 capability operation 配置并确保敏感值默认脱敏
- [ ] 5.3 重构 `doctor`，按 `search`、`docs.search`、`docs.tree`、`docs.read`、`fetch`、`map` 报告可用性、连接和单点能力状态
- [ ] 5.4 实现 `diagnose search|docs|fetch|map`，其中 docs 分别检查 search/tree/read，并输出脱敏失败阶段、延迟和建议
- [ ] 5.5 实现普通输出与 `--debug` metadata 隔离，并验证日志不污染 stdout JSON
- [ ] 5.6 保留并分组 `skills status|update`，将 regression/provider 测试迁移到开发测试入口或隐藏命令
- [ ] 5.7 提交“CLI 运维与诊断”阶段 commit

## 6. 其他旧接口迁移

- [ ] 6.1 将仍有同等新操作的 provider 专用顶层命令改为默认帮助隐藏的薄兼容入口，映射到 `search`、`docs search|tree|read`、`fetch`、`map`
- [ ] 6.2 为 `route`、`route-calibrate`、`smoke`、`regression` 和 `model` 定义隐藏、开发入口或弃用行为，不恢复 AnySearch/Deep Research
- [ ] 6.3 确保旧入口不再被 Agent skill 引用，并在 README 记录兼容期、替代操作和计划删除版本
- [ ] 6.4 运行旧 CLI 契约回归与新版契约测试，确认兼容层不复制 provider 业务逻辑
- [ ] 6.5 提交“旧 CLI 迁移兼容层”阶段 commit

## 7. 文档、Skill 与发布验证

- [ ] 7.1 更新 `README.zh-CN.md` 和 `README.md`，说明四类能力、`docs search|tree|read`、内部 provider 对应、配置化 fallback 与维护命令
- [ ] 7.2 在 README 中明确 `map` 是站内 URL/链接结构探索，不是单页结构化提取或仓库目录读取
- [ ] 7.3 同步更新 `skills/smart-search-cli/` 与 `src/smart_search/assets/skills/smart-search-cli/`，只向 Agent 教授四类能力及 docs 子操作
- [ ] 7.4 更新命令契约、provider routing、setup/config、回归发布等 skill references，并验证公开副本与打包副本完全一致
- [ ] 7.5 在迁移文档说明 AnySearch 与 Deep Research 已移除，paper-search/垂直搜索将在独立 change 中处理
- [ ] 7.6 重新检查 OpenSpec 规格、最终实现、测试和用户文档的一致性，解决所有偏差
- [ ] 7.7 运行 `python -m compileall -q src tests`、相关 pytest、完整 `python -m pytest tests -q`、`npm test` 和 `git diff --check`
- [ ] 7.8 检查最终 `git diff`、`git status`、敏感信息及跨平台路径兼容，并提交发布准备阶段 commit
