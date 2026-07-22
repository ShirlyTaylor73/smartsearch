# Smart Search 仓库协作指南

本文档是 AI 助手在本仓库工作的主要入口。除系统级指令和用户当前明确要求外，应以本文档为准；不要依赖特定的 agent harness、任务编排器或会话恢复工具才能完成日常开发。

## 基本原则

1. 默认使用中文沟通和编写项目文档。代码标识符、命令、协议字段、第三方专有名词及错误信息保留英文。
2. 先理解需求和现有实现，再提出方案。处理仓库问题时，优先阅读本地代码、测试、配置和最新文档，不根据历史任务记录猜测当前行为。
3. 对代码仓库进行实质性修改前，必须取得用户明确批准。批准前可以调查、复现、分析和拟定方案，但不得修改代码、配置或项目文档。
4. 保持改动范围聚焦。不得顺带重构无关模块，也不得覆盖或撤销用户已有的工作区修改。
5. 使用 Git 跟踪工作。修改前后检查 `git status` 和 `git diff`，每个完整阶段形成独立、可恢复的 commit。
6. 涉及复杂或核心逻辑时采用聚焦测试覆盖；优先先补充失败测试，再实现修复，并在结束前运行相关测试。

## 事实来源与优先级

判断当前需求、行为和约束时，按以下顺序取证：

1. 用户当前对话中的明确要求和批准。
2. 当前工作区中的代码、测试及项目配置。
3. `README.zh-CN.md`、`README.md` 和代码旁的维护文档。
4. Git 历史，用于理解改动背景，不用于覆盖当前代码事实。
5. `.trellis/` 等历史工作流资料，仅在需要追溯旧设计时参考。

当资料冲突时，应指出冲突并以更高优先级来源为准。外部技术资料应优先采用项目或依赖的最新官方文档，并记录关键版本或链接。

### Provider 官方参考与强制核对规则

新增、修改、删除、排查或评审任何 provider 相关代码前，必须先核对对应 provider 的最新官方资料，再确定 endpoint、认证方式、请求参数、响应结构、流式协议、错误语义、重试条件和能力边界。该要求同样适用于已经从默认集合移除、计划删除、仅保留兼容入口或曾经进入设计讨论的 provider。

资料获取顺序如下：

1. 若 Context7 能解析对应官方 library，先使用 `smart-search docs resolve` 和 `smart-search docs search` 获取版本化文档。
2. Context7 没有覆盖时，使用当前 Smart Search CLI 的 Tavily-backed source discovery、`map site` 或 `fetch content`，并将检索范围限定到下表中的官方域名。
3. MCP 官方页面未给出 input schema 时，连接官方 endpoint 执行只读 `tools/list`，以实际 schema 为准。
4. 官方文档、官方 SDK 和 live schema 冲突时，优先级为 live schema / 当前 OpenAPI、当前官方 API reference、当前官方 SDK、仓库现有实现与历史记录。
5. 不得使用第三方教程、聚合站、搜索摘要或模型记忆替代官方资料。第三方页面只能用于发现官方入口，不能作为 provider contract 的依据。
6. 实现记录、commit/PR 说明或最终反馈中必须列出实际参考的官方链接和核对日期；需要真实凭据但未执行的 live 验证必须明确说明。

#### 当前保留或候选保留的 Provider

| Provider / adapter | 仓库中的对应范围 | 官方资料 |
|---|---|---|
| xAI Responses / Grok | `XAI_API_*`、`xai_responses.py`、`search.answer` | [xAI REST API Reference](https://docs.x.ai/developers/rest-api-reference/inference/chat)、[Tools Overview](https://docs.x.ai/developers/tools/overview)、[Web Search](https://docs.x.ai/developers/tools/web-search)、[X Search](https://docs.x.ai/developers/tools/x-search) |
| OpenAI-compatible transport | `OPENAI_COMPATIBLE_*`、`openai_compatible.py` | [OpenAI Chat Completions Overview](https://developers.openai.com/api/reference/chat-completions/overview)、[Create Chat Completion](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。OpenAI 文档只定义协议基线；修改自定义 relay 兼容性时还必须读取目标 endpoint 运营方的官方文档，不能假设所有 OpenAI-compatible 服务完全一致 |
| Exa | `EXA_*`、`exa.py`、来源搜索 | [Search API Guide](https://docs.exa.ai/docs/reference/search-api-guide)、[Search API Reference](https://docs.exa.ai/docs/reference/search)、[官方 Python SDK](https://github.com/exa-labs/exa-py)。涉及旧 `findSimilar` 时必须先核对 SDK 的 deprecated 标记，不得沿用旧文档假设 |
| Context7 | `CONTEXT7_*`、`context7.py`、文档 resolve/search | [Context7 API Guide](https://context7.com/docs/api-guide)、[官方仓库](https://github.com/upstash/context7) |
| Zhipu MCP ZRead | `ZHIPU_MCP_API_KEY`、`ZHIPU_MCP_ZREAD_API_URL`、`zhipu_mcp.py` 的仓库工具 | [Coding Plan MCP 总览](https://docs.bigmodel.cn/cn/coding-plan/mcp)、[ZRead MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/zread-mcp-server)。修改 `search_doc`、`get_repo_structure`、`read_file` 前必须再次执行 `tools/list`；当前已知 schema 不包含 `ref` |
| Firecrawl | `FIRECRAWL_*`、Search/Scrape/JSON/Map 调用 | [Search API](https://docs.firecrawl.dev/api-reference/endpoint/search)、[Scrape API](https://docs.firecrawl.dev/api-reference/endpoint/scrape)、[Map API](https://docs.firecrawl.dev/api-reference/endpoint/map)、[官方文档索引](https://docs.firecrawl.dev/llms.txt) |

#### 已移除、计划移除或历史讨论过的 Provider

| Provider | 历史范围 | 官方资料与注意事项 |
|---|---|---|
| Zhipu REST Web Search | `ZHIPU_API_KEY`、`zhipu.py` | [工具 API 总览](https://docs.bigmodel.cn/api-reference/%E5%B7%A5%E5%85%B7-api/)、[网络搜索 API](https://docs.bigmodel.cn/api-reference/%E5%B7%A5%E5%85%B7-api/%E7%BD%91%E7%BB%9C%E6%90%9C%E7%B4%A2)。该凭据与 Coding Plan MCP key 不得混用 |
| Zhipu MCP Web Search | `ZHIPU_MCP_SEARCH_API_URL`、`web_search_prime` | [联网搜索 MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/search-mcp-server)、[Coding Plan MCP 总览](https://docs.bigmodel.cn/cn/coding-plan/mcp) |
| Zhipu MCP Web Reader | `ZHIPU_MCP_READER_API_URL`、`webReader` | [网页读取 MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/reader-mcp-server)、[Coding Plan MCP 总览](https://docs.bigmodel.cn/cn/coding-plan/mcp) |
| Tavily | Search、Extract、Map 与 fallback | [Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)、[Extract API](https://docs.tavily.com/documentation/api-reference/endpoint/extract)、[Map API](https://docs.tavily.com/documentation/api-reference/endpoint/map) |
| Jina Reader | `JINA_*`、`jina.py`、URL/PDF Reader | [Reader 官方页面](https://jina.ai/reader)、[Reader API Dashboard](https://jina.ai/api-dashboard/reader)。匿名 `r.jina.ai` 与带 key 的 API 行为不得视为完全相同 |
| AnySearch | 已删除的 vertical/domain/batch/extract MCP provider | [AnySearch 官方站](https://www.anysearch.com)、[官方 MCP Server 仓库](https://github.com/anysearch-ai/anysearch-mcp-server)。未发现独立、稳定的公开 API reference；若恢复集成，必须以官方仓库和 live `tools/list` 重新建立 contract，不得照搬历史实现 |
| DeepWiki | 曾作为 ZRead 替代方案讨论，当前未实现 | [DeepWiki MCP](https://docs.devin.ai/work-with-devin/deepwiki-mcp)、[DeepWiki](https://deepwiki.com)。若未来接入，必须区分面向人类的 DeepWiki 页面与 MCP 工具契约 |

智谱相关 provider 仍有额外强制要求：涉及 `ZHIPU_API_KEY` 对应的 REST provider，或 `ZHIPU_MCP_API_KEY` 对应的 MCP Search、Reader、ZRead provider 时，必须先通过 Tavily/Smart Search 读取上述对应官方页面的最新内容；若涉及共享认证或能力边界，必须同时交叉核对 REST 与 Coding Plan MCP 文档。

## 仓库结构

- `src/smart_search/`：Python CLI、服务、配置、路由及 provider 实现。
- `src/smart_search/assets/skills/`：随 Python 包发布的 skill 资源；改动时注意与仓库根目录对应资源保持一致。
- `skills/smart-search-cli/`：仓库内可直接维护的 Smart Search skill。
- `tests/`：pytest 测试。
- `npm/`：npm 包装器及其测试脚本。
- `scripts/`：开发、验证和维护脚本。
- `README.zh-CN.md`、`README.md`：面向用户的中英文说明。

新增文件前先确认其应归属的模块。修改 CLI 契约、配置字段、provider 行为或发布资源时，应同时检查对应测试、README 和打包配置是否需要同步。

## 标准开发流程

### 1. 调查与澄清

- 检查 `git status`，识别并保留现有工作区修改。
- 使用 `rg`、测试和最小复现定位相关代码路径。
- 明确目标行为、非目标、兼容性要求和验收条件。
- 多文件新功能应从粗到细确认需求。需要固化规格时，可使用用户指定的规格工具，或在 `docs/` 下编写中文规格文档。
- 超大型产品请求应拆成多个可独立验收和提交的开发周期，并记录总体目标及各周期边界。

### 2. 请求批准

在首次实质性修改前，向用户说明：

- 已确认的问题或需求；
- 计划修改的文件和行为；
- 测试及兼容性策略；
- 已知风险或尚未确定的事项。

只有在用户明确批准后才能进入实现。若批准后需求范围发生实质变化，应重新说明影响并再次确认。

### 3. 实现

- 遵循现有模块边界、命名和代码风格。
- 优先复用已有 helper、provider contract 和 CLI 输出结构。
- 不在代码中引入对某个 agent harness、个人目录或本地会话状态的运行时依赖。
- 对复杂逻辑先在 `tests/` 中添加聚焦测试，再完成实现。
- 只添加能解释非显然约束的简短注释。

### 4. 验证

根据改动范围选择最小但充分的验证集：

```bash
python -m compileall -q src tests
python -m pytest tests -q
npm test
```

窄范围修改可先运行单个测试文件或 `pytest -k`；涉及共享契约、CLI、打包或发布流程时，应扩大到完整相关测试。需要真实 provider 凭据或联网的验证不得伪装为已通过，应明确说明未运行的部分及原因。

### 5. 检查与提交

- 检查 `git diff --check`、`git diff` 和最终 `git status`。
- 确认规格、实现、测试和用户文档没有相互矛盾。
- 每个完整阶段创建一个主题明确的 commit，提交信息应说明实际改动目的。
- 不将无关的未跟踪文件或用户改动纳入 commit。
- 最终反馈应包含主要改动、验证结果、commit 标识及仍存在的风险。

## Trellis 与其他工作流工具

`.trellis/` 中的 spec、task、workspace journal 等内容是历史参考资料，不是当前核心工作流，也不是有效任务状态的权威来源。

- 不要求安装、初始化或调用 Trellis。
- 不使用 Trellis command、hook、agent、task 或 journal 驱动开发、恢复会话或判定完成状态。
- 不因历史 Trellis 记录缺失、过期或互相矛盾而阻塞正常开发。
- 除非用户明确要求整理或删除历史资料，否则保留 `.trellis/` 内容，不主动迁移或改写。

OpenSpec、平台 skill、subagent 和其他辅助工具均为可选能力。仅在用户明确要求或任务确实需要时使用；它们不得取代本文件规定的需求澄清、用户批准、代码验证和 Git 提交流程。

## 安全与兼容性

- 不提交密钥、token、个人配置、真实 provider 凭据或本地绝对路径。
- 不执行破坏性 Git 或文件操作，除非用户明确要求并确认影响。
- 保持 Python `>=3.10` 兼容，并关注 Windows、macOS 和 Linux 的路径及终端差异。
- CLI 的 JSON、Markdown 和 content 输出属于用户可见契约；修改字段、退出码、fallback 或流式行为时必须考虑向后兼容和回归测试。
- 修改 `skills/smart-search-cli/` 时，同时检查 `src/smart_search/assets/skills/smart-search-cli/` 的发布副本，避免安装后的 skill 与仓库版本漂移。
