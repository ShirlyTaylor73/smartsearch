# Smart Search

`smart-search` is a deterministic retrieval CLI for AI agents. Agents choose task operations; every operation has one responsible provider, while credentials and endpoints remain maintainer configuration. There is no cross-provider fallback.

## Install

Install the CLI globally for regular search commands:

```bash
npm install -g @shirlytaylor73/smart-search@latest
smart-search --version
smart-search setup
```

Interactive `smart-search setup` offers to install the bundled Agent skill after provider configuration. You can also install it independently with this package's own `npx` command, without a prior global CLI installation:

```bash
npx --yes --package=@shirlytaylor73/smart-search@latest \
  smart-search skills install --project --agent codex --yes
```

Project installs keep one canonical copy at `<project>/.agents/skills/smart-search-cli/`. Other Agent directories link to that copy by default. To target multiple Agents:

```bash
npx --yes --package=@shirlytaylor73/smart-search@latest \
  smart-search skills install --project \
  --agent codex --agent claude --agent cursor --yes
```

Global installs use `--global` and keep the canonical copy at `~/.agents/skills/smart-search-cli/`. Windows prefers directory junctions. If directory links are unavailable, installation falls back to copies; pass `--copy` to select copying explicitly.

Current targets: `codex`, `claude`, `cursor`, `opencode`, `copilot`, `gemini`, `kiro`, `qoder`, `codebuddy`, `droid`, `pi`, `kilo`, `antigravity`, `windsurf`, and `hermes`.

Manage an existing installation independently:

```bash
smart-search skills status --project --agent codex --yes
smart-search skills update --project --agent codex --yes
smart-search skills uninstall --project --agent codex --yes
```

The CLI source is Python under `src/smart_search/`. The npm package is a cross-platform launcher that creates the Python environment and runs `python -m smart_search.cli`.

## Commands and Responsible Providers

| Command | Provider / Tool |
|---|---|
| `search answer QUERY` | Grok via the configured xAI Responses or OpenAI-compatible transport |
| `search sources QUERY` | Exa Search `/search` |
| `docs resolve NAME [QUERY]` | Context7 library search |
| plain `docs search QUERY` | Context7 context lookup |
| `docs search QUERY --source owner/repo` | Zhipu MCP ZRead `search_doc` |
| `docs tree REPO [--path PATH]` | ZRead `get_repo_structure` |
| `docs read REPO PATH` | ZRead `read_file` |
| `fetch content URL` | Firecrawl Scrape Markdown |
| `fetch extract URL` | Firecrawl Scrape JSON |
| `map site URL` | Firecrawl Map |

```bash
smart-search search answer "important AI agent news today" --format markdown
smart-search search sources "agent context retrieval" --limit 5 --include-highlights
smart-search docs resolve nextjs "app router"
smart-search docs search "recent important PRs" --source owner/repo
smart-search docs tree owner/repo --path src
smart-search docs read owner/repo README.md --format content
smart-search fetch content https://example.com/article --format content
smart-search fetch extract https://example.com/product --schema '{"type":"object","properties":{"name":{"type":"string"}}}'
smart-search map site https://docs.example.com --search authentication --sitemap include --limit 50
```

Firecrawl Map defaults are `sitemap=include`, include subdomains, ignore query parameters, use cache, and `limit=5000`. CLI timeout values are seconds and are converted to milliseconds. `--location` accepts JSON such as `{"country":"US","languages":["en-US"]}`.

## Configuration

| Provider | Configuration |
|---|---|
| Grok | `SMART_SEARCH_GROK_TRANSPORT=xai-responses|openai-compatible` plus the selected transport URL/key/model |
| Exa | `EXA_API_KEY`, `EXA_BASE_URL`, `EXA_TIMEOUT_SECONDS`, `EXA_SEARCH_TYPE` |
| Context7 | `CONTEXT7_API_KEY`, `CONTEXT7_BASE_URL`, `CONTEXT7_TIMEOUT_SECONDS` |
| ZRead | `ZHIPU_MCP_API_KEY`, `ZHIPU_MCP_ZREAD_API_URL`, `ZHIPU_MCP_TIMEOUT_SECONDS` |
| Firecrawl | `FIRECRAWL_API_KEY`, `FIRECRAWL_API_URL`, `FIRECRAWL_TIMEOUT_SECONDS` |

`EXA_SEARCH_TYPE` accepts `instant|fast|auto|deep-lite|deep|deep-reasoning` and defaults to `auto`. `SMART_SEARCH_OPERATION_TIMEOUTS` only overrides known operation budgets, for example `{"search.answer":120,"map.site":180}`.

```bash
smart-search config path
smart-search config list
smart-search doctor
smart-search diagnose search sources
smart-search diagnose provider firecrawl
```

If the responsible provider is missing or fails, the operation stops with a stable error category. It never calls a different provider.

## 0.3.0 Migration

| Removed contract | Replacement |
|---|---|
| provider ordering, feature negotiation, fallback | fixed operation executor |
| `search similar` / `exa-similar` | removed; deprecated Exa Find Similar has no equivalent redirect |
| `search sources --mode` | configure `EXA_SEARCH_TYPE` |
| `docs tree/read --ref` | removed because ZRead does not support ref |
| Tavily Map depth/instruction flags | Firecrawl search, sitemap, subdomain, query, cache, and location flags |
| Tavily, Jina, Zhipu REST, Zhipu MCP Search/Reader, DeepWiki | removed |
| fallback/operation-chain config keys | removed and ignored when found in old config files |

Maintenance commands remain: `setup`, `doctor`, `config`, `skills install|uninstall|status|update`, `diagnose`, `dev regression`, help, and version.

## Verify

```bash
python -m compileall -q src tests
python -m pytest tests -q
npm test
smart-search diagnose smoke --mode mock
```

The current stable release is `0.3.1` and uses the npm dist-tag `latest`.
