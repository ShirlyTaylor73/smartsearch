# Provider 接口兼容性修复

核对日期：2026-10-15。范围为 Context7、ZRead 和 OpenAI-compatible 的响应读取；个人配置、relay 升级与 Firecrawl 抽取内容质量不在本次修改范围。2026-10-16 用户批准提交、推送及发布 0.3.5。

## 官方依据与验收约定

- [Context7 API Guide](https://context7.com/docs/api-guide)、[Library Search](https://context7.com/docs/api-reference/search/search-for-libraries)：resolve 使用 `/api/v2/libs/search`，独立传递 `libraryName` 和 `query`；CLI 未给 QUERY 时以 NAME 填充官方必填 query。
- [Context7 Search](https://context7.com/docs/api-reference/search/search-documentation-in-one-request)：无 source 查询调用 `/api/v3/search?type=json`，自动选库。provider 层支持可选 library、version、language；本周期不增加 CLI 参数。
- [Context7 Context](https://context7.com/docs/api-reference/context/get-documentation-context)：指定 source 使用 `/api/v2/context?type=json`；支持 slash 和 `@` 版本 ID，保留 library redirect。正文渲染为 Markdown，代码/说明片段及版本元数据保留在 JSON 输出中，来源取 `codeId`、`pageId`。无来源字段的片段留在正文中，不制造引用 URL。
- [ZRead MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/zread-mcp-server)：官方 endpoint 的 live `tools/list` 已核实 search_doc(repo_name, query, language)、get_repo_structure(repo_name, dir_path)、read_file(repo_name, file_path)，无 ref；实际协商协议版本为 `2024-11-05`。保留现有请求与认证方式。
- ZRead live `tools/call` 证实正文有 JSON 字符串包装，解码后仍可能有字面换行分隔符。最多解码两层 JSON 字符串，保留 raw_content；引用解析识别 Source 行和编号标题。字面换行仅用于解析视图，不全局替换正文中代码字符串的转义。
- [HTTPX QuickStart](https://www.python-httpx.org/quickstart/#streaming-responses)：流式响应需先读取才可访问 text；错误响应先 `aread()` 再 `raise_for_status()`，保留真实 HTTP 状态和响应体。

Context7 错误通过原有 error_type/error 契约返回，并补充 http_status、provider_error_code（上游提供时）。成功返回的 version、rules、library_id 和 redirected_from 按实际响应保留。网络超时、非 JSON 错误响应、202 索引中状态不得误报成功。

## 验证

聚焦回归覆盖新旧文档路由、版本 ID、真实来源、JSON 格式参数、错误透传，ZRead 多来源/转义/多个 MCP 文本块/文件内容保持，以及流式 HTTP 401/426/429 响应读取。真实验收使用本仓库源码 CLI 和既有用户级配置，串行执行 ZRead，避免并发限流。

2026-10-15 验证结果：

- Python 全量测试通过；compileall 和 git diff --check 通过。
- npm test 通过，包含 Python 测试、包装器修复测试、npx skill 安装测试、CLI 入口和 npm pack --dry-run。首次尝试受沙箱网络限制，允许联网后通过。包清单不含个人 config.json。
- docs resolve fastapi 成功，候选首项为 FastAPI 官方文档。
- 无 source 的 FastAPI Depends 查询成功，返回 FastAPI/SQLModel 相关文档与实际来源；指定 /fastapi/fastapi 的查询也成功，按官方返回处理 library redirect。
- ZRead search_doc 成功，5 条来源 URL 均无字面换行或 excerpt 污染；docs tree --path src 与 docs read README.md 成功。
- diagnose docs search/tree 均通过。这两项验证配置与执行器状态；真实请求成功由前述查询单独验证。
- 再次直连官方 ZRead tools/list：三个工具名称、全部字符串参数、required 和 additionalProperties=false 均与契约一致，无 ref。
- Grok HTTP 426/401/429 使用实际 HTTPX 流对象进行模拟验证；未代替用户升级或重测 relay。Firecrawl 本轮未改动、未重测。

README 中英文版本与 bundled skill 的 docs 指南已同步。skill 仅补充执行当前 CLI 所需的直接搜索与 source 用法，修复背景保留在本文。

发布前检查（2026-10-16）：242 项测试通过；Grok answer、Exa sources、Context7 resolve、ZRead tree、Firecrawl content 最小真实调用均成功。GitHub 登录有效，本机 npm whoami 返回 401；工作流使用 OIDC Trusted Publishing，不依赖本机 npm 登录或长期 npm token。根目录 config.json 已加入 gitignore，npm 发布文件白名单不包含私人配置。
