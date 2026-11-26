# Smart Search

`smart-search` is a deterministic retrieval CLI for AI agents. Agents choose task operations; every operation has one responsible provider, while credentials and endpoints remain maintainer configuration. There is no cross-provider fallback.

## Install

Install the CLI globally for regular search commands:

```bash
npm install -g @shirlytaylor73/smart-search@latest
smart-search --version
smart-search setup
```

Interactive `smart-search setup` asks for the `search answer` base URL, API key and model, uses arrow-key selection for the skill scope, Space for multi-selecting Agent targets, and Y/N confirmations. API key input is hidden. Existing values are confirmed one by one and kept by default; configuration and bundled skill installation start only after the final confirmation.

Environment-provided values are shown as externally managed and are never copied into the config file. Esc/Ctrl-C cancels before writing and exits with status 130. Pipes and CI do not fall back to text menus; use explicit options instead:

```bash
smart-search setup --non-interactive \
  --search-answer-api-url https://api.x.ai/v1 \
  --search-answer-api-key "$SEARCH_ANSWER_API_KEY" \
  --search-answer-model "<model>"
```

Non-interactive setup sends no requests by default. With `--probe-tools` it checks search tool support but only reports; it never rewrites `SEARCH_ANSWER_TOOLS`.

You can also install the skill independently with this package's own `npx` command, without a prior global CLI installation:

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
smart-search skills install       # interactive arrow-key/Space selection
smart-search skills status --project --agent codex --yes
smart-search skills update --project --agent codex --yes
smart-search skills uninstall --project --agent codex --yes
```

`skills install|update|uninstall|status` share the same scope and Agent selectors. In non-TTY environments, pass `--project` or `--global`, one or more `--agent` values, and `--yes` for mutating operations.

The CLI source is Python under `src/smart_search/`. The npm package is a cross-platform launcher that creates the Python environment and runs `python -m smart_search.cli`.

## Commands and Responsible Providers

| Command | Provider / Tool |
|---|---|
| `search answer QUERY` | Streaming Responses API (`POST {base_url}/responses`), always with search tools |
| `search sources QUERY` | Exa Search `/search` |
| `docs resolve NAME [QUERY]` | Context7 `/api/v2/libs/search` |
| plain `docs search QUERY` | Context7 `/api/v3/search`, automatic library selection |
| `docs search QUERY --source /owner/library` | Context7 `/api/v2/context`, explicit library |
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
smart-search fetch extract https://www.python.org/downloads/ --prompt "Extract the latest stable Python 3 release"
smart-search fetch extract https://example.com/product --schema '{"type":"object","properties":{"name":{"type":"string"}}}'
smart-search map site https://docs.example.com --search authentication --sitemap include --limit 50
```

`fetch extract` requires at least one of `--prompt` or `--schema`; both may be combined. Prompt-only extraction lets Firecrawl infer the output structure, while a schema constrains it.

For documentation questions, include the product name in `docs search QUERY` to search directly. Use `docs resolve NAME [QUERY]` when you want to choose an explicit documentation source. Context7 IDs also accept `/owner/library/version` and `/owner/library@version`. Documentation results include original source URLs and readable content; returned version metadata is preserved when supplied by Context7.

Firecrawl Map defaults are `sitemap=include`, include subdomains, ignore query parameters, use cache, and `limit=5000`. CLI timeout values are seconds and are converted to milliseconds. `--location` accepts JSON such as `{"country":"US","languages":["en-US"]}`.

## Configuration

| Provider | Configuration |
|---|---|
| Responses (`search answer`) | `SEARCH_ANSWER_API_URL`, `SEARCH_ANSWER_API_KEY`, `SEARCH_ANSWER_MODEL`, `SEARCH_ANSWER_TOOLS` |
| Exa | `EXA_API_KEY`, `EXA_BASE_URL`, `EXA_TIMEOUT_SECONDS`, `EXA_SEARCH_TYPE` |
| Context7 | `CONTEXT7_API_KEY`, `CONTEXT7_BASE_URL`, `CONTEXT7_TIMEOUT_SECONDS` |
| ZRead | `ZHIPU_MCP_API_KEY`, `ZHIPU_MCP_ZREAD_API_URL`, `ZHIPU_MCP_TIMEOUT_SECONDS` |
| Firecrawl | `FIRECRAWL_API_KEY`, `FIRECRAWL_API_URL`, `FIRECRAWL_TIMEOUT_SECONDS` |

### `search answer`

Official xAI, OpenAI and relays all receive the same request; only configuration differs:

| Key | Meaning |
|---|---|
| `SEARCH_ANSWER_API_URL` | Required base URL; requests go to `/responses` under it. Official xAI: `https://api.x.ai/v1` |
| `SEARCH_ANSWER_API_KEY` | Required |
| `SEARCH_ANSWER_MODEL` | Required and sent as is; there is no default model |
| `SEARCH_ANSWER_TOOLS` | Optional comma list of `web_search`, `x_search`; default `web_search`. `x_search` is an xAI tool, so leave it out for other vendors' models |

Every request uses `stream=true` and `tool_choice="required"`. The endpoint must support `/responses`, the configured tools and `tool_choice`. Otherwise the error is returned as is: there is no `/chat/completions` fallback and no retry with parameters removed. `tool_choice="required"` makes the model call a tool; it does not make the answer or its citations correct, so verify important claims with `fetch content`. Sources come from the API's `url_citation` annotations.

An explicit `--timeout` is used as given; otherwise the `search.answer` entry of `SMART_SEARCH_OPERATION_TIMEOUTS` applies, defaulting to 120 seconds. `--debug` adds a redacted `debug` object with tool call counts, response status, token usage and request attempts.

### Search tool probe

Interactive `setup` (first run and reruns alike) saves the configuration, then checks `web_search` and `x_search` separately. It asks before changing the tool list. A tool counts as supported only when the request completes and reports a tool call. Timeouts, rate limits, auth failures and missing call records are `unknown` and never change configuration. A failed probe does not undo the saved values.

```bash
smart-search doctor --probe-tools   # read-only recheck
```

The probe sends real requests that may be billed; X search is billed per post and user profile fetched. Editing or importing the config file takes effect immediately; `search answer` never probes or rewrites configuration.

`EXA_SEARCH_TYPE` accepts `instant|fast|auto|deep-lite|deep|deep-reasoning` and defaults to `auto`. `SMART_SEARCH_OPERATION_TIMEOUTS` only overrides known operation budgets, for example `{"search.answer":120,"map.site":180}`.

```bash
smart-search config path
smart-search config list
smart-search doctor
smart-search doctor --probe-tools
smart-search diagnose search sources
smart-search diagnose provider firecrawl
```

If the responsible provider is missing or fails, the operation stops with a stable error category. It never calls a different provider.

## `search answer` configuration migration

The two former transports are now one. `SMART_SEARCH_GROK_TRANSPORT`, `OPENAI_COMPATIBLE_*` and `XAI_*` are no longer read at runtime.

| Old key | New key |
|---|---|
| `OPENAI_COMPATIBLE_API_URL` / `XAI_API_URL` | `SEARCH_ANSWER_API_URL` (set `https://api.x.ai/v1` explicitly if you relied on the xAI default) |
| `OPENAI_COMPATIBLE_API_KEY` / `XAI_API_KEY` | `SEARCH_ANSWER_API_KEY` |
| `OPENAI_COMPATIBLE_MODEL` / `XAI_MODEL` | `SEARCH_ANSWER_MODEL` |
| `XAI_TOOLS` | `SEARCH_ANSWER_TOOLS` (the default is now `web_search`) |
| `SMART_SEARCH_GROK_TRANSPORT`, `OPENAI_COMPATIBLE_STREAM` | removed |

Interactive `smart-search setup` reads the set the old release actually used (chosen by `SMART_SEARCH_GROK_TRANSPORT`) from the config file and asks before reusing each value. The tool list is not migrated; the probe suggests it. Old keys stay in the file so an older install keeps working; remove them with `config unset` once unused. Non-interactive setup and environment variables must switch to the new keys by hand.

Services that only offer `/chat/completions` no longer work. The `:online` model suffix is no longer appended for OpenRouter URLs.

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

The current stable release is `0.3.4` and uses the npm dist-tag `latest`.
