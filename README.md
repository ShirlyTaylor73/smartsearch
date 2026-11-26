# Smart Search

A retrieval CLI for AI agents. Pick the command that matches the task; each command uses one fixed provider and returns an error if it fails.

[简体中文](README.zh-CN.md)

## Install

Requires Node.js 18+ and Python 3.10+.

```bash
npm install -g @shirlytaylor73/smart-search
smart-search setup
smart-search doctor
```

## Configuration

`smart-search setup` prompts for each setting and can install the Agent skill. Reruns keep existing values by default. After upgrading from an older version, it offers to reuse the old `search answer` settings.

Use non-interactive mode in scripts and CI:

```bash
smart-search setup --non-interactive \
  --search-answer-api-url https://api.x.ai/v1 \
  --search-answer-api-key "$SEARCH_ANSWER_API_KEY" \
  --search-answer-model "<model>"
```

You can also edit single keys. Environment variables take precedence over the config file.

```bash
smart-search config path
smart-search config list                  # secrets are masked
smart-search config set EXA_API_KEY <key>
smart-search config unset EXA_API_KEY
```

| Used by | Required | Optional |
|---|---|---|
| `search answer` | `SEARCH_ANSWER_API_URL`, `SEARCH_ANSWER_API_KEY`, `SEARCH_ANSWER_MODEL` | `SEARCH_ANSWER_TOOLS` |
| `search sources` | `EXA_API_KEY` | `EXA_BASE_URL`, `EXA_SEARCH_TYPE`, `EXA_TIMEOUT_SECONDS` |
| `docs resolve`, `docs search` | `CONTEXT7_API_KEY` | `CONTEXT7_BASE_URL`, `CONTEXT7_TIMEOUT_SECONDS` |
| `docs` commands on GitHub repositories | `ZHIPU_MCP_API_KEY` | `ZHIPU_MCP_ZREAD_API_URL`, `ZHIPU_MCP_TIMEOUT_SECONDS` |
| `fetch`, `map` | `FIRECRAWL_API_KEY` | `FIRECRAWL_API_URL`, `FIRECRAWL_TIMEOUT_SECONDS` |

- `SEARCH_ANSWER_API_URL`: base URL of a Responses API: official xAI (`https://api.x.ai/v1`), OpenAI, or a relay. The endpoint must support `/responses`, the chosen search tools and `tool_choice`.
- `SEARCH_ANSWER_TOOLS`: comma-separated `web_search` (default) and `x_search`. `x_search` works with Grok only.
- `EXA_SEARCH_TYPE`: `auto` (default), `instant`, `fast`, `deep-lite`, `deep`, or `deep-reasoning`.
- `SMART_SEARCH_OPERATION_TIMEOUTS`: total timeout per command in seconds, e.g. `{"search.answer":300,"map.site":180}`.

### Search tool probe

After saving, interactive `setup` checks `web_search` and `x_search`, and asks before changing the tool list. Run `smart-search doctor --probe-tools` to recheck without changing configuration. Non-interactive setup only probes with `--probe-tools`, and only reports.

The probe sends real requests, which may be billed.

## Commands

| Command | Purpose | Provider |
|---|---|---|
| `search answer QUERY` | Search the web and answer | Responses API |
| `search sources QUERY` | Find source links | Exa |
| `docs resolve NAME [QUERY]` | Find a documentation library ID | Context7 |
| `docs search QUERY` | Search documentation | Context7; ZRead for repositories |
| `docs tree REPO` | List repository files | ZRead |
| `docs read REPO PATH` | Read a repository file | ZRead |
| `fetch content URL` | Convert a page to Markdown | Firecrawl |
| `fetch extract URL` | Extract structured data | Firecrawl |
| `map site URL` | List the links of a site | Firecrawl |

All of these accept `--format json|markdown|content` (default `json`), `--output FILE` and `--debug`. Run any command with `--help` for all options.

### search

```bash
smart-search search answer "important AI agent news today" --format markdown
smart-search search answer "survey related work on a topic" --timeout 300

smart-search search sources "agent context retrieval" --limit 5 --include-highlights
```

- `answer`: times out after 120 seconds by default; raise it with `--timeout` for complex questions. Every request calls a search tool. Verify important claims against the sources with `fetch content`.
- `sources`: accepts `--include-domains`, `--exclude-domains`, `--start-published-date`, `--category`, `--include-text` and `--include-highlights`.

### docs

```bash
smart-search docs search "how does caching work in the Next.js app router"

smart-search docs resolve nextjs "app router"
smart-search docs search "app router" --source /vercel/next.js

smart-search docs search "recent important PRs" --source owner/repo
smart-search docs tree owner/repo --path src
smart-search docs read owner/repo README.md --format content
```

`--source /owner/library` selects a Context7 library; add a version as `/owner/library/version` or `/owner/library@version`. `--source owner/repo` (no leading slash) searches a GitHub repository.

### fetch

```bash
smart-search fetch content https://example.com/article --format content

smart-search fetch extract https://www.python.org/downloads/ --prompt "Extract the latest Python 3 version"
smart-search fetch extract https://example.com/product \
  --schema '{"type":"object","properties":{"name":{"type":"string"}}}'
```

`extract` needs `--prompt` or `--schema`; both may be used together.

### map

```bash
smart-search map site https://docs.example.com --search authentication --limit 50
```

By default it reads the sitemap, includes subdomains, ignores query parameters and returns up to 5000 links. Adjust with `--sitemap include|skip|only`, `--no-include-subdomains`, `--no-ignore-query-parameters`, `--ignore-cache`, `--timeout` and `--location '{"country":"US","languages":["en-US"]}'`.

## Troubleshooting

```bash
smart-search doctor                       # configuration state of every command
smart-search doctor --probe-tools         # live check of search tool support
smart-search diagnose search answer       # configuration of one command
smart-search diagnose provider firecrawl  # configuration of one provider
smart-search search answer "test" --debug  # request details and tool call counts
```

Failed results carry an `error_type`: `config_error`, `parameter_error`, `auth_error`, `rate_limited`, `timeout`, `network_error`, `parse_error`, or `provider_error`.

## Agent skill

Install the skill without installing the CLI globally:

```bash
npx @shirlytaylor73/smart-search skills install --project --agent codex --yes
```

With the CLI installed globally:

```bash
smart-search skills install        # choose scope and Agents interactively
smart-search skills install --global --agent codex --agent claude --yes
smart-search skills status --global --agent codex --yes
smart-search skills update --global --agent codex --yes
smart-search skills uninstall --global --agent codex --yes
```

- `--project` installs into `.agents/skills/` in the current project, `--global` into `~/.agents/skills/`. Other Agent directories link there; pass `--copy` to copy instead.
- Supported Agents: `codex`, `claude`, `cursor`, `opencode`, `copilot`, `gemini`, `kiro`, `qoder`, `codebuddy`, `droid`, `pi`, `kilo`, `antigravity`, `windsurf`, `hermes`.

## Development

The source is in `src/smart_search/`. The npm package creates the Python environment and launches the CLI.

```bash
python -m compileall -q src tests
python -m pytest tests -q
npm test
smart-search diagnose smoke --mode mock
```
