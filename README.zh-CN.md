# Smart Search

`smart-search` 是面向 AI Agent 的确定性检索 CLI。Agent 只选择任务命令；每个 operation 的 provider 固定，凭据和 endpoint 由维护者配置，不存在跨 provider fallback。

## 安装

日常执行搜索命令时，全局安装 CLI：

```bash
npm install -g @shirlytaylor73/smart-search@latest
smart-search --version
smart-search setup
```

交互式 `smart-search setup` 依次询问 `search answer` 的地址、API key 和模型，使用方向键选择 skill scope，Agent 目标使用空格多选，确认操作使用 Y/N；API key 输入会隐藏。向导会逐项确认已有配置，默认保留，并在最终确认后统一保存配置和安装 bundled Agent skill。

环境变量中的配置会标记为外部管理，不会被复制进配置文件。Esc/Ctrl-C 会在写入前取消并返回退出码 130。管道、CI 等非 TTY 环境不会退回到手输菜单，应使用显式参数：

```bash
smart-search setup --non-interactive \
  --search-answer-api-url https://api.x.ai/v1 \
  --search-answer-api-key "$SEARCH_ANSWER_API_KEY" \
  --search-answer-model "<模型名>"
```

非交互模式默认不发起任何请求；加 `--probe-tools` 会检测搜索工具支持情况，但只报告结果，不改写 `SEARCH_ANSWER_TOOLS`。

也可使用本包自己的 `npx` 命令单独安装 skill，无需预先全局安装 CLI：

```bash
npx --yes --package=@shirlytaylor73/smart-search@latest \
  smart-search skills install --project --agent codex --yes
```

项目级安装将实体文件保存到 `<project>/.agents/skills/smart-search-cli/`，其他 Agent 目录默认通过链接指向该目录。多 Agent 安装：

```bash
npx --yes --package=@shirlytaylor73/smart-search@latest \
  smart-search skills install --project \
  --agent codex --agent claude --agent cursor --yes
```

全局安装使用 `--global`，canonical 目录为 `~/.agents/skills/smart-search-cli/`。Windows 优先使用 directory junction；链接不可用时自动降级为复制，也可用 `--copy` 显式选择复制。

当前 target：`codex`、`claude`、`cursor`、`opencode`、`copilot`、`gemini`、`kiro`、`qoder`、`codebuddy`、`droid`、`pi`、`kilo`、`antigravity`、`windsurf`、`hermes`。

独立管理命令：

```bash
smart-search skills install       # 方向键/空格交互选择
smart-search skills status --project --agent codex --yes
smart-search skills update --project --agent codex --yes
smart-search skills uninstall --project --agent codex --yes
```

`skills install|update|uninstall|status` 共用相同的 scope 和 Agent 选择界面。非 TTY 环境使用 `--project`/`--global`、一个或多个 `--agent`，变更操作再加 `--yes`。

Python 源码位于 `src/smart_search/`；npm 包只是跨平台启动包装器，安装时创建 Python 环境并调用 `python -m smart_search.cli`。

## 命令与唯一 Provider

| 命令 | 唯一 Provider / Tool |
|---|---|
| `search answer QUERY` | 流式 Responses API（`POST {base_url}/responses`），固定带搜索工具 |
| `search sources QUERY` | Exa Search `/search` |
| `docs resolve NAME [QUERY]` | Context7 `/api/v2/libs/search` |
| 普通 `docs search QUERY` | Context7 `/api/v3/search`，自动选择文档库 |
| `docs search QUERY --source /owner/library` | Context7 `/api/v2/context`，指定文档库 |
| `docs search QUERY --source owner/repo` | Zhipu MCP ZRead `search_doc` |
| `docs tree REPO [--path PATH]` | ZRead `get_repo_structure` |
| `docs read REPO PATH` | ZRead `read_file` |
| `fetch content URL` | Firecrawl Scrape Markdown |
| `fetch extract URL` | Firecrawl Scrape JSON |
| `map site URL` | Firecrawl Map |

```bash
smart-search search answer "今天 AI Agent 有什么重要新闻？" --format markdown
smart-search search sources "agent context retrieval" --limit 5 --include-highlights
smart-search docs resolve nextjs "app router"
smart-search docs search "最近的重要 PR" --source owner/repo
smart-search docs tree owner/repo --path src
smart-search docs read owner/repo README.md --format content
smart-search fetch content https://example.com/article --format content
smart-search fetch extract https://www.python.org/downloads/ --prompt "提取最新的 Python 3 正式版本"
smart-search fetch extract https://example.com/product --schema '{"type":"object","properties":{"name":{"type":"string"}}}'
smart-search map site https://docs.example.com --search authentication --sitemap include --limit 50
```

`fetch extract` 至少需要 `--prompt` 或 `--schema` 之一，也可以同时提供。仅使用 prompt 时由 Firecrawl 推断输出结构，schema 用于约束结构。

文档问题可直接通过 `docs search QUERY` 查询，在问题中写明产品名称。需要指定文档来源时，先运行 `docs resolve NAME [QUERY]` 选择 ID。Context7 ID 同时支持 `/owner/library/version` 和 `/owner/library@version`。文档结果提供原始来源 URL 和可读正文；Context7 返回版本信息时会一并保留。

`map site` 默认使用 `sitemap=include`、包含子域名、忽略 query 参数、不忽略缓存、`limit=5000`。`--timeout` 单位为秒，内部转换为 Firecrawl 的毫秒；`--location` 接受 `{"country":"US","languages":["en-US"]}`。

## 配置

主要配置键：

| Provider | 配置 |
|---|---|
| Responses（`search answer`） | `SEARCH_ANSWER_API_URL`、`SEARCH_ANSWER_API_KEY`、`SEARCH_ANSWER_MODEL`、`SEARCH_ANSWER_TOOLS` |
| Exa | `EXA_API_KEY`、`EXA_BASE_URL`、`EXA_TIMEOUT_SECONDS`、`EXA_SEARCH_TYPE` |
| Context7 | `CONTEXT7_API_KEY`、`CONTEXT7_BASE_URL`、`CONTEXT7_TIMEOUT_SECONDS` |
| ZRead | `ZHIPU_MCP_API_KEY`、`ZHIPU_MCP_ZREAD_API_URL`、`ZHIPU_MCP_TIMEOUT_SECONDS` |
| Firecrawl | `FIRECRAWL_API_KEY`、`FIRECRAWL_API_URL`、`FIRECRAWL_TIMEOUT_SECONDS` |

### `search answer`

xAI 官方、OpenAI 或中转站使用同一种请求，仅由配置区分：

| 配置键 | 说明 |
|---|---|
| `SEARCH_ANSWER_API_URL` | 必填，base URL，请求发往其后的 `/responses`；xAI 官方为 `https://api.x.ai/v1` |
| `SEARCH_ANSWER_API_KEY` | 必填 |
| `SEARCH_ANSWER_MODEL` | 必填，原样发送，没有默认模型 |
| `SEARCH_ANSWER_TOOLS` | 可选，逗号分隔的 `web_search`、`x_search`，默认 `web_search`。`x_search` 是 xAI 工具，不要用于其他厂商的模型 |

每次请求固定使用 `stream=true` 和 `tool_choice="required"`。端点必须同时支持 `/responses`、所选工具和 `tool_choice`；不支持时如实报错，不会改走 `/chat/completions`，也不会去掉参数重试。`tool_choice="required"` 只要求模型调用工具，不保证回答和引用正确，重要结论仍应用 `fetch content` 核对来源。回答来源取自接口返回的 `url_citation` 标注。

`--timeout` 显式传值时按该值生效；未传时使用 `SMART_SEARCH_OPERATION_TIMEOUTS` 中的 `search.answer`，缺省 120 秒。`--debug` 输出脱敏的 `debug` 对象，包括工具调用次数、响应状态、token 用量和请求尝试记录。

### 搜索工具检测

交互式 `setup`（首次和重跑相同）先保存配置，再分别检测 `web_search` 和 `x_search`。建议值与当前值不同时会先询问，确认后才修改。只有请求完成且返回了工具调用记录才判为支持；超时、限流、鉴权失败或没有调用记录一律为 `unknown`，不会自动改配置。检测失败不影响已保存的配置。

```bash
smart-search doctor --probe-tools   # 只读复测，不修改配置
```

检测会发起真实请求并可能计费；X 搜索按抓取的帖子和用户资料计费。直接编辑或导入配置文件即时生效，`search answer` 运行时不做检测，也不改写配置。

`EXA_SEARCH_TYPE` 允许 `instant|fast|auto|deep-lite|deep|deep-reasoning`，默认 `auto`。`SMART_SEARCH_OPERATION_TIMEOUTS` 只允许配置已知 operation 的总超时，例如：

```json
{"search.answer":120,"map.site":180}
```

配置优先级为环境变量高于配置文件。查看位置和脱敏配置：

```bash
smart-search config path
smart-search config list
smart-search doctor
smart-search doctor --probe-tools
smart-search diagnose search sources
smart-search diagnose provider firecrawl
```

唯一 provider 缺失或失败时立即返回 `config_error`、`parameter_error`、`auth_error`、`rate_limited`、`timeout`、`network_error`、`parse_error` 或 `provider_error`，不会尝试其他 provider。

## `search answer` 配置迁移

旧的两个通道已合并。`SMART_SEARCH_GROK_TRANSPORT`、`OPENAI_COMPATIBLE_*` 和 `XAI_*` 在运行时不再读取。

| 旧键 | 新键 |
|---|---|
| `OPENAI_COMPATIBLE_API_URL` / `XAI_API_URL` | `SEARCH_ANSWER_API_URL`（原来依赖 xAI 默认地址的需显式填写 `https://api.x.ai/v1`） |
| `OPENAI_COMPATIBLE_API_KEY` / `XAI_API_KEY` | `SEARCH_ANSWER_API_KEY` |
| `OPENAI_COMPATIBLE_MODEL` / `XAI_MODEL` | `SEARCH_ANSWER_MODEL` |
| `XAI_TOOLS` | `SEARCH_ANSWER_TOOLS`（默认值变为 `web_search`） |
| `SMART_SEARCH_GROK_TRANSPORT`、`OPENAI_COMPATIBLE_STREAM` | 删除 |

交互式 `smart-search setup` 会读取配置文件中旧版实际生效的那一套（按 `SMART_SEARCH_GROK_TRANSPORT` 判断），逐项询问是否沿用；工具列表不迁移，由检测给出建议。旧键保留在文件中，以便旧版本继续使用；确认不再需要后可用 `config unset` 清理。非交互模式和环境变量需要手动改用新键。

只支持 `/chat/completions` 的服务不再可用。不再自动给 OpenRouter 地址的模型名追加 `:online`。

## 0.3.0 迁移

| 旧契约 | 新契约 |
|---|---|
| 多 provider 顺序、feature negotiation、fallback | 删除；每个 operation 固定 executor |
| `search similar` / `exa-similar` | 删除；Exa `findSimilar` 已 deprecated，无语义等价转发 |
| `search sources --mode` | 删除；维护者用 `EXA_SEARCH_TYPE` |
| `docs tree/read --ref` | 删除；ZRead 当前 schema 不支持 ref |
| Tavily `map --instructions/--max-depth/--max-breadth` | 使用 Firecrawl `--search`、`--sitemap`、subdomain/query/cache/location 参数 |
| Tavily、Jina、Zhipu REST、Zhipu MCP Search/Reader、DeepWiki | 删除 |
| `SMART_SEARCH_FALLBACK_MODE`、`SMART_SEARCH_OPERATION_CONFIG`、`OPENAI_COMPATIBLE_FALLBACK_MODELS` | 删除；旧配置键读取时忽略，可用 `config unset` 手动清理旧文件 |

功能性命令仍包括 `setup`、`doctor`、`config path|list|set|unset`、`skills install|uninstall|status|update`、完整 `diagnose`、`dev regression`、`-h/--help` 和 `-v/--version`。

## 验证

```bash
python -m compileall -q src tests
python -m pytest tests -q
npm test
smart-search diagnose smoke --mode mock
```

当前稳定版为 `0.3.4`，npm dist-tag 使用 `latest`。
