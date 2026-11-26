# Smart Search

面向 AI Agent 的检索 CLI。按任务选择命令，每个命令固定使用一个 provider，失败时直接返回错误。

[English](README.md)

## 安装

需要 Node.js 18+ 和 Python 3.10+。

```bash
npm install -g @shirlytaylor73/smart-search
smart-search setup
smart-search doctor
```

## 配置

`smart-search setup` 交互式填写各项配置，并可安装 Agent skill。重跑时默认保留已有值；从旧版升级时，会询问是否沿用旧的 `search answer` 配置。

脚本或 CI 中使用非交互模式：

```bash
smart-search setup --non-interactive \
  --search-answer-api-url https://api.x.ai/v1 \
  --search-answer-api-key "$SEARCH_ANSWER_API_KEY" \
  --search-answer-model "<模型名>"
```

也可以单独读写配置项。环境变量优先于配置文件。

```bash
smart-search config path
smart-search config list                  # 密钥脱敏显示
smart-search config set EXA_API_KEY <key>
smart-search config unset EXA_API_KEY
```

| 用途 | 必填 | 可选 |
|---|---|---|
| `search answer` | `SEARCH_ANSWER_API_URL`、`SEARCH_ANSWER_API_KEY`、`SEARCH_ANSWER_MODEL` | `SEARCH_ANSWER_TOOLS` |
| `search sources` | `EXA_API_KEY` | `EXA_BASE_URL`、`EXA_SEARCH_TYPE`、`EXA_TIMEOUT_SECONDS` |
| `docs resolve`、`docs search` | `CONTEXT7_API_KEY` | `CONTEXT7_BASE_URL`、`CONTEXT7_TIMEOUT_SECONDS` |
| GitHub 仓库的 `docs` 命令 | `ZHIPU_MCP_API_KEY` | `ZHIPU_MCP_ZREAD_API_URL`、`ZHIPU_MCP_TIMEOUT_SECONDS` |
| `fetch`、`map` | `FIRECRAWL_API_KEY` | `FIRECRAWL_API_URL`、`FIRECRAWL_TIMEOUT_SECONDS` |

- `SEARCH_ANSWER_API_URL`：支持 Responses API 的 base URL，可以是 xAI 官方（`https://api.x.ai/v1`）、OpenAI 或中转站。端点需要支持 `/responses`、所选搜索工具和 `tool_choice`。
- `SEARCH_ANSWER_TOOLS`：`web_search`（默认）、`x_search`，逗号分隔。`x_search` 仅适用于 Grok。
- `EXA_SEARCH_TYPE`：`auto`（默认）、`instant`、`fast`、`deep-lite`、`deep`、`deep-reasoning`。
- `SMART_SEARCH_OPERATION_TIMEOUTS`：各命令的总超时（秒），如 `{"search.answer":300,"map.site":180}`。

### 搜索工具检测

交互式 `setup` 保存配置后会检测 `web_search` 和 `x_search`，修改工具列表前先询问。之后可用 `smart-search doctor --probe-tools` 复测，此命令不修改配置。非交互模式默认不检测，加 `--probe-tools` 后只报告结果。

检测会发送真实请求，可能计费。

## 命令

| 命令 | 用途 | Provider |
|---|---|---|
| `search answer QUERY` | 联网搜索并回答 | Responses API |
| `search sources QUERY` | 查找来源链接 | Exa |
| `docs resolve NAME [QUERY]` | 查找文档库 ID | Context7 |
| `docs search QUERY` | 搜索文档 | Context7；仓库来源用 ZRead |
| `docs tree REPO` | 查看仓库目录 | ZRead |
| `docs read REPO PATH` | 读取仓库文件 | ZRead |
| `fetch content URL` | 网页转 Markdown | Firecrawl |
| `fetch extract URL` | 提取结构化数据 | Firecrawl |
| `map site URL` | 列出站点链接 | Firecrawl |

以上命令都支持 `--format json|markdown|content`（默认 `json`）、`--output FILE` 和 `--debug`。完整参数见各命令的 `--help`。

### search

```bash
smart-search search answer "今天 AI Agent 有什么重要新闻？" --format markdown
smart-search search answer "梳理某方向的相关工作" --timeout 300

smart-search search sources "agent context retrieval" --limit 5 --include-highlights
```

- `answer`：默认超时 120 秒，复杂问题可用 `--timeout` 放宽。每次都会调用搜索工具，重要结论请用 `fetch content` 核对来源。
- `sources`：支持 `--include-domains`、`--exclude-domains`、`--start-published-date`、`--category`、`--include-text`、`--include-highlights`。

### docs

```bash
smart-search docs search "Next.js app router 如何做缓存"

smart-search docs resolve nextjs "app router"
smart-search docs search "app router" --source /vercel/next.js

smart-search docs search "最近的重要 PR" --source owner/repo
smart-search docs tree owner/repo --path src
smart-search docs read owner/repo README.md --format content
```

`--source /owner/library` 指定 Context7 文档库，版本可写作 `/owner/library/version` 或 `/owner/library@version`。`--source owner/repo`（无开头斜杠）搜索 GitHub 仓库。

### fetch

```bash
smart-search fetch content https://example.com/article --format content

smart-search fetch extract https://www.python.org/downloads/ --prompt "提取最新的 Python 3 版本"
smart-search fetch extract https://example.com/product \
  --schema '{"type":"object","properties":{"name":{"type":"string"}}}'
```

`extract` 需要 `--prompt` 或 `--schema`，两者可同时使用。

### map

```bash
smart-search map site https://docs.example.com --search authentication --limit 50
```

默认读取 sitemap、包含子域名、忽略 query 参数，最多返回 5000 条。可用 `--sitemap include|skip|only`、`--no-include-subdomains`、`--no-ignore-query-parameters`、`--ignore-cache`、`--timeout` 和 `--location '{"country":"US","languages":["en-US"]}'` 调整。

## 排障

```bash
smart-search doctor                       # 检查各命令的配置状态
smart-search doctor --probe-tools         # 实测搜索工具支持情况
smart-search diagnose search answer       # 检查单个命令的配置
smart-search diagnose provider firecrawl  # 检查单个 provider 的配置
smart-search search answer "测试" --debug  # 查看请求详情和工具调用次数
```

失败结果中的 `error_type`：`config_error`、`parameter_error`、`auth_error`、`rate_limited`、`timeout`、`network_error`、`parse_error`、`provider_error`。

## Agent skill

无需全局安装 CLI，可直接安装 skill：

```bash
npx @shirlytaylor73/smart-search skills install --project --agent codex --yes
```

全局安装 CLI 后：

```bash
smart-search skills install        # 交互选择范围和 Agent
smart-search skills install --global --agent codex --agent claude --yes
smart-search skills status --global --agent codex --yes
smart-search skills update --global --agent codex --yes
smart-search skills uninstall --global --agent codex --yes
```

- `--project` 安装到当前项目的 `.agents/skills/`，`--global` 安装到 `~/.agents/skills/`。其他 Agent 目录通过链接指向这里；加 `--copy` 改为复制。
- 支持的 Agent：`codex`、`claude`、`cursor`、`opencode`、`copilot`、`gemini`、`kiro`、`qoder`、`codebuddy`、`droid`、`pi`、`kilo`、`antigravity`、`windsurf`、`hermes`。

## 开发

源码位于 `src/smart_search/`，npm 包负责创建 Python 环境并启动 CLI。

```bash
python -m compileall -q src tests
python -m pytest tests -q
npm test
smart-search diagnose smoke --mode mock
```
