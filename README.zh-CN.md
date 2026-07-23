# Smart Search

`smart-search` 是面向 AI Agent 的确定性检索 CLI。Agent 只选择任务命令；每个 operation 的 provider 固定，凭据和 endpoint 由维护者配置，不存在跨 provider fallback。

## 安装

日常执行搜索命令时，全局安装 CLI：

```bash
npm install -g @shirlytaylor73/smart-search@next
smart-search --version
smart-search setup
```

交互式 `smart-search setup` 在保存 provider 配置后会询问是否安装 bundled Agent skill。也可使用本包自己的 `npx` 命令单独安装，无需预先全局安装 CLI：

```bash
npx --yes --package=@shirlytaylor73/smart-search@next \
  smart-search skills install --project --agent codex --yes
```

项目级安装将实体文件保存到 `<project>/.agents/skills/smart-search-cli/`，其他 Agent 目录默认通过链接指向该目录。多 Agent 安装：

```bash
npx --yes --package=@shirlytaylor73/smart-search@next \
  smart-search skills install --project \
  --agent codex --agent claude --agent cursor --yes
```

全局安装使用 `--global`，canonical 目录为 `~/.agents/skills/smart-search-cli/`。Windows 优先使用 directory junction；链接不可用时自动降级为复制，也可用 `--copy` 显式选择复制。

当前 target：`codex`、`claude`、`cursor`、`opencode`、`copilot`、`gemini`、`kiro`、`qoder`、`codebuddy`、`droid`、`pi`、`kilo`、`antigravity`、`windsurf`、`hermes`。

独立管理命令：

```bash
smart-search skills status --project --agent codex --yes
smart-search skills update --project --agent codex --yes
smart-search skills uninstall --project --agent codex --yes
```

Python 源码位于 `src/smart_search/`；npm 包只是跨平台启动包装器，安装时创建 Python 环境并调用 `python -m smart_search.cli`。

## 命令与唯一 Provider

| 命令 | 唯一 Provider / Tool |
|---|---|
| `search answer QUERY` | Grok；由 `SMART_SEARCH_GROK_TRANSPORT` 选择 xAI Responses 或 OpenAI-compatible |
| `search sources QUERY` | Exa Search `/search` |
| `docs resolve NAME [QUERY]` | Context7 library search |
| 普通 `docs search QUERY` | Context7 context lookup |
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
smart-search fetch extract https://example.com/product --schema '{"type":"object","properties":{"name":{"type":"string"}}}'
smart-search map site https://docs.example.com --search authentication --sitemap include --limit 50
```

`map site` 默认使用 `sitemap=include`、包含子域名、忽略 query 参数、不忽略缓存、`limit=5000`。`--timeout` 单位为秒，内部转换为 Firecrawl 的毫秒；`--location` 接受 `{"country":"US","languages":["en-US"]}`。

## 配置

主要配置键：

| Provider | 配置 |
|---|---|
| Grok | `SMART_SEARCH_GROK_TRANSPORT=xai-responses|openai-compatible`，以及所选 transport 的 URL/key/model |
| Exa | `EXA_API_KEY`、`EXA_BASE_URL`、`EXA_TIMEOUT_SECONDS`、`EXA_SEARCH_TYPE` |
| Context7 | `CONTEXT7_API_KEY`、`CONTEXT7_BASE_URL`、`CONTEXT7_TIMEOUT_SECONDS` |
| ZRead | `ZHIPU_MCP_API_KEY`、`ZHIPU_MCP_ZREAD_API_URL`、`ZHIPU_MCP_TIMEOUT_SECONDS` |
| Firecrawl | `FIRECRAWL_API_KEY`、`FIRECRAWL_API_URL`、`FIRECRAWL_TIMEOUT_SECONDS` |

`EXA_SEARCH_TYPE` 允许 `instant|fast|auto|deep-lite|deep|deep-reasoning`，默认 `auto`。`SMART_SEARCH_OPERATION_TIMEOUTS` 只允许配置已知 operation 的总超时，例如：

```json
{"search.answer":120,"map.site":180}
```

配置优先级为环境变量高于配置文件。查看位置和脱敏配置：

```bash
smart-search config path
smart-search config list
smart-search doctor
smart-search diagnose search sources
smart-search diagnose provider firecrawl
```

唯一 provider 缺失或失败时立即返回 `config_error`、`parameter_error`、`auth_error`、`rate_limited`、`timeout`、`network_error`、`parse_error` 或 `provider_error`，不会尝试其他 provider。

## 0.3.0-beta 迁移

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

发布版本线为 `0.3.0-beta.N`，npm dist-tag 使用 `next`。
