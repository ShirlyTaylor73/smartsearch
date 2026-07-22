## 1. 契约固化与官方 schema 核对

- [x] 1.1 重新核对本 change 的 proposal、design 与两份 spec，确认固定 provider 责任矩阵、breaking 边界和非目标一致
- [x] 1.2 对照 Exa 官方 Search API 与 Python SDK，记录当前 type 枚举并确认 `find_similar/findSimilar` 已 deprecated
- [x] 1.3 对照 Firecrawl 官方 Scrape JSON/Markdown 与 Map 文档，确定 `sitemap`、location schema、默认值、limit 和毫秒 timeout 映射
- [x] 1.4 通过 ZRead 官方文档与 MCP `tools/list` 固定 `search_doc`、`get_repo_structure`、`read_file` 的实际 input schema
- [x] 1.5 在 `tests/` 先添加公开命令 → 唯一 provider/tool、禁止 fallback、删除 `search similar`、`--mode`、旧参数/命令的失败测试
- [x] 1.6 提交契约测试阶段 commit，并复核测试失败原因只来自尚未实现的新契约

## 2. 确定性配置与 Operation Executor

- [x] 2.1 添加 `SMART_SEARCH_GROK_TRANSPORT` 的配置解析、允许值校验、脱敏展示和 config source 追踪测试
- [x] 2.2 添加 `EXA_SEARCH_TYPE` 当前原生枚举校验与默认 `auto` 测试，并拒绝 `neural|keyword`
- [x] 2.3 删除 `SMART_SEARCH_FALLBACK_MODE`、`SMART_SEARCH_OPERATION_CONFIG` provider 链与 `OPENAI_COMPATIBLE_FALLBACK_MODELS` 的执行语义
- [x] 2.4 添加仅允许 operation timeout override 的 `SMART_SEARCH_OPERATION_TIMEOUTS` 配置契约与边界测试
- [x] 2.5 将 operation profile 重构为固定 executor、必需配置、默认 timeout 与 normalizer descriptor，且不注册 `search.similar`
- [x] 2.6 删除 provider candidate、feature negotiation、fallback runner 和 attempts 聚合路径
- [x] 2.7 统一固定 executor 的配置、参数、认证、限流、超时、网络、解析与 provider 错误分类并补充脱敏测试
- [x] 2.8 运行配置与 operation executor 聚焦测试，检查 diff 后提交确定性路由阶段 commit

## 3. Search 与 Docs 固定 Provider 实现

- [x] 3.1 修改 `search answer` 只执行配置选中的 Grok transport，删除公开 `--stream/--no-stream` 和跨 transport fallback
- [x] 3.2 修改 `search sources` 只调用 Exa Search，删除公开 `--mode`，使用配置的原生 type 并验证时间、domain、category、text、highlights 与 limit payload
- [x] 3.3 删除 `search similar` parser/service、deprecated Exa Find Similar adapter 和相关输出/诊断路径
- [x] 3.4 修改 `docs resolve` 只调用 Context7 library resolve/search
- [x] 3.5 实现 Context7 library id 与 GitHub `owner/repo` 的 source 解析、歧义处理和本地参数校验
- [x] 3.6 修改 `docs search` 对普通文档只调用 Context7、对 `owner/repo` 只调用 ZRead `search_doc`
- [x] 3.7 为 ZRead `search_doc.language` 实现 `zh|en` 语言推导/默认策略及测试
- [x] 3.8 修改 `docs tree` 只传 `repo_name`/`dir_path`、`docs read` 只传 `repo_name`/`file_path`，删除所有 `ref` 传递
- [x] 3.9 运行 search/docs/provider payload 聚焦测试，检查 diff 后提交 Search/Docs 阶段 commit

## 4. Firecrawl 承接 Fetch 与 Map

- [x] 4.1 将 Firecrawl 请求封装收敛为可测试 adapter，统一认证、timeout、重试、错误映射和响应脱敏
- [x] 4.2 实现 `fetch content` 的 Firecrawl Scrape Markdown/正文请求与最终 URL/来源规范化
- [x] 4.3 完成 `fetch extract` 的 Firecrawl JSON Schema 请求，验证 `--schema` 并使 `--max-length` 只限制 `raw_evidence`
- [x] 4.4 实现 Firecrawl Map 请求与 `--search`、`--sitemap`、subdomain/query 双向布尔开关、cache、`1..100000` limit、秒转毫秒 timeout、country/languages location 映射
- [x] 4.5 从 `map site` parser 删除 `--instructions`、`--max-depth`、`--max-breadth` 并添加明确迁移错误/帮助测试
- [x] 4.6 验证 fetch/map 的公共 envelope、Markdown/content renderer 与输出文件行为保持稳定
- [x] 4.7 运行 Firecrawl adapter 和 fetch/map 聚焦测试，检查 diff 后提交 Firecrawl 阶段 commit

## 5. 删除非最小 Provider 与旧兼容层

- [x] 5.1 删除 Tavily、Jina、Zhipu REST Search、Zhipu MCP Search/Reader、DeepWiki 的代码入口和 provider registry 描述
- [x] 5.2 删除上述 provider 的配置属性、setup 提示、doctor/smoke fixture 与测试环境变量
- [x] 5.3 保留 Zhipu MCP ZRead adapter，删除其 web search/reader 方法和不符合实际 schema 的 ref 兼容代码
- [x] 5.4 删除 provider 专用隐藏 CLI 命令与 alias 转发，并确保旧 `exa-similar` 不会转发到普通 Search
- [x] 5.5 删除普通输出中的 `provider_attempts`、`fallback_used` 等候选链字段，同时保留 debug 的单 provider 脱敏元数据
- [x] 5.6 使用 `rg` 检查已删除 provider、fallback、feature negotiation 与旧参数没有运行时残留
- [x] 5.7 运行删除行为与 import/compile 聚焦测试，检查 diff 后提交清理阶段 commit

## 6. Setup、Doctor 与 Diagnose

- [x] 6.1 重做 setup，使其选择单一 Grok transport 并只配置 Exa、Context7、ZRead、Firecrawl 所需凭据
- [x] 6.2 更新 `config path|list|set|unset` 的允许键、旧键忽略/清理提示和密钥脱敏测试
- [x] 6.3 更新 doctor，按每个公开 operation 输出 `responsible_provider`、必需配置和 executor 可用性
- [x] 6.4 更新 `diagnose search|docs|fetch|map`，search 只含 `answer|sources`，并移除 candidates/single-provider/fallback 状态
- [x] 6.5 将 `diagnose provider` 限定为 xAI Responses、OpenAI-compatible、Exa、Context7、ZRead、Firecrawl 并区分配置检查与真实连接检查
- [x] 6.6 保持 `diagnose route|route-calibrate|smoke`、`dev regression`、skills、help 和 version 功能可用且不参与 provider 路由
- [x] 6.7 运行 setup/config/doctor/diagnose 聚焦测试，检查 diff 后提交维护命令阶段 commit

## 7. 文档、Skill 与 Breaking Release

- [x] 7.1 更新 `README.zh-CN.md`，加入完整“能力/子命令 → 唯一 provider/tool”表、凭据表和失败策略
- [x] 7.2 更新 `README.md`，与中文 README 的命令、参数、配置和迁移内容保持一致
- [x] 7.3 编写从多 provider/fallback、旧 provider 命令、`search similar`、`search sources --mode`、ZRead `--ref`、Tavily Map 参数迁移到新版契约的对照表
- [x] 7.4 同步更新 `skills/smart-search-cli/` 与 `src/smart_search/assets/skills/smart-search-cli/`，确保 Agent 不管理 provider
- [x] 7.5 更新 npm wrapper、Python/package metadata 和发布测试到 `0.3.0-beta.x` 版本线
- [x] 7.6 检查 README、skill、CLI help、OpenSpec 规格和实际 parser 没有相互矛盾
- [x] 7.7 检查 diff 后提交文档与发布契约阶段 commit

## 8. 完整验证与交付

- [ ] 8.1 运行 `python -m compileall -q src tests`
- [ ] 8.2 运行全部 `python -m pytest tests -q`
- [ ] 8.3 运行 `npm test` 和发布资源/安装包装器相关测试
- [ ] 8.4 运行 mock smoke、CLI regression 与所有 help/version 示例
- [ ] 8.5 在凭据可用时分别实际测试 Grok、Exa Search、Context7、ZRead、Firecrawl；如未运行必须明确记录原因，不得伪装通过
- [ ] 8.6 重新检查 proposal、design、两份 spec 与全部任务完成情况，并运行 OpenSpec validate
- [ ] 8.7 运行 `git diff --check`、检查敏感信息和最终 `git status`，提交验证/收尾 commit
