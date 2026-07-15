# Smart Search

`smart-search` 是面向 AI Agent 和命令行用户的 CLI-first 网络与技术文档检索工具。Agent 只选择任务 operation；provider、凭据、优先级、feature 匹配、超时和 fallback 由配置与内部服务层管理。

## 安装与初始化

```bash
npm install -g @konbakuyomu/smart-search
smart-search setup
smart-search doctor --format json
```

也可以使用 Python 包：

```bash
pip install -e .
smart-search --version
```

## 四大查询能力

### search：网络回答与来源发现

```bash
smart-search search answer "今天有哪些 AI 政策更新" --format json
smart-search search sources "agentic search papers" --limit 5 --mode semantic --include-highlights --format json
smart-search search similar https://example.com/article --limit 5 --format json
```

`search sources` 支持 provider 无关的 `--limit`、`--mode semantic|keyword|auto`、`--start-published-date`、`--include-domains`、`--exclude-domains`、`--category`、`--include-text`、`--include-highlights`。不支持必需 feature 的 provider 会被自动排除。

### docs：技术文档与代码仓库

```bash
smart-search docs resolve react hooks --format json
smart-search docs search "useEffect cleanup" --format json
smart-search docs search "最近的重要 PR" --source owner/repo --format json
smart-search docs tree owner/repo --path src --ref main --format json
smart-search docs read owner/repo README.md --ref main --format content
```

### fetch：已知 URL 内容

```bash
smart-search fetch content https://example.com/article --format content
smart-search fetch extract https://example.com/product --schema '{"type":"object"}' --format json
```

- `fetch content` 返回适合阅读、总结和引用的正文或 Markdown。
- `fetch extract` 返回结构化 `data` 和可选 `raw_evidence`，不会用普通 Markdown 冒充结构化结果。

### map：站点结构探索

```bash
smart-search map site https://docs.example.com \
  --instructions "查找认证和限流页面" \
  --max-depth 1 \
  --max-breadth 20 \
  --limit 50 \
  --timeout 150 \
  --format json
```

`map site` 发现站内 URL、路径和链接结构。它不是单页内容提取，也不是代码仓库目录读取；后两者分别使用 `fetch content` 和 `docs tree`。

## Operation 与 Provider

| Operation | 内部候选 |
|---|---|
| `search.answer` | xAI Responses、OpenAI-compatible |
| `search.sources` | Exa、智谱 Web Search、智谱 MCP、Tavily、Firecrawl |
| `search.similar` | Exa |
| `docs.resolve` | Context7 |
| `docs.search` | Context7、Exa、智谱 MCP zread |
| `docs.tree` | 智谱 MCP zread |
| `docs.read` | 智谱 MCP zread |
| `fetch.content` | Tavily、Jina、智谱 MCP Reader、Firecrawl |
| `fetch.extract` | Firecrawl 结构化抽取 |
| `map.site` | Tavily |

Fallback 只在同一个 operation 内发生。例如 `docs.tree` 不会 fallback 到 Context7，`fetch.extract` 不会 fallback 到普通正文。

可用 `SMART_SEARCH_OPERATION_CONFIG` 配置 operation 顺序、禁用项、超时和 fallback，值为 JSON object；普通 Agent 无需读取或修改它。

## 配置与排查

```bash
smart-search setup
smart-search config path
smart-search config list
smart-search config set KEY VALUE
smart-search config unset KEY
smart-search doctor --format markdown

smart-search diagnose search sources
smart-search diagnose docs tree
smart-search diagnose fetch extract
smart-search diagnose map site
smart-search diagnose provider openai-compatible
smart-search diagnose route "React API docs"
smart-search diagnose route-calibrate
smart-search diagnose smoke --mode mock
```

主要凭据包括 `XAI_API_KEY`、`OPENAI_COMPATIBLE_API_URL`、`OPENAI_COMPATIBLE_API_KEY`、`EXA_API_KEY`、`CONTEXT7_API_KEY`、`ZHIPU_API_KEY`、`ZHIPU_MCP_API_KEY`、`JINA_API_KEY`、`TAVILY_API_KEY`、`FIRECRAWL_API_KEY`。`config list` 默认脱敏。

## 输出与退出码

所有查询 operation 支持：

```bash
--format json|markdown|content
--output PATH
--debug
```

公共 JSON 包含 `ok`、`capability`、`operation`、`content`、`sources`、`elapsed_ms`。退出码：`0` 成功、`2` 参数错误、`3` 配置错误、`4` 网络/能力错误、`5` 运行时错误。

## 迁移

旧 provider 命令在兼容期内隐藏并映射到新 operation，例如 `exa-search` → `search sources`、`exa-similar` → `search similar`、`context7-library` → `docs resolve`、旧 `fetch` → `fetch content`、旧 `map` → `map site`。

实验性垂直 provider 与 Deep Research CLI 已移除。研究分解、证据对比和最终写作由上层 Agent 负责；论文与垂直检索后续通过独立 paper-search 扩展。

## 开发验证

```bash
smart-search dev regression
python -m compileall -q src tests
python -m pytest tests -q
npm test
```

## 发布通道

稳定版使用 Git tag 和 npm `latest`。测试版使用
`<package.json version>-beta.N` 并发布到 npm `next`；例如前两个测试版
之后可以发布 `0.1.10-beta.3`。稳定版 GitHub Release 的正文来自
`.github/releases/vX.Y.Z.md`。

npm 版本不可变，已发布版本不能原地改名，只能用新的 beta 版本替代。

发布收尾检查：

1. 先运行 `npm view` 并通过
   `gh release list --repo konbakuyomu/smartsearch --limit 100` 核对现状。
2. 遇到 npm `E409` 时，先确认版本是否已经存在，再串行重试。
3. 兼容窗口内可运行旧入口 `smart-search regression` 和
   `smart-search smoke --mock --format json` 验证迁移提示；新版入口分别是
   `smart-search dev regression` 和
   `smart-search diagnose smoke --mode mock --format json`。
4. Windows 包装层额外执行非 ASCII JSON 管道，并用
   PowerShell `ConvertFrom-Json` 验证输出。
