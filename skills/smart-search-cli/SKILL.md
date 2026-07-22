---
name: smart-search-cli
description: "Deterministic CLI-first web, documentation, URL extraction, and site mapping for AI agents."
---

# Smart Search CLI

Use the local `smart-search` command. Select operations by task intent; never select, reorder, or retry providers.

## Query operations

- `smart-search search answer QUERY --format json`: current-web answer.
- `smart-search search sources QUERY --limit 5 --format json`: source discovery.
- `smart-search docs resolve NAME [QUERY] --format json`: resolve a Context7 library id.
- `smart-search docs search QUERY [--source SOURCE] --format json`: search library docs or `owner/repo` knowledge.
- `smart-search docs tree REPO [--path PATH] --format json`: inspect repository structure.
- `smart-search docs read REPO PATH --format content`: read a repository file.
- `smart-search fetch content URL --format content`: retrieve readable content.
- `smart-search fetch extract URL [--schema JSON] --format json`: extract structured data.
- `smart-search map site URL [--search TEXT] --limit 50 --format json`: discover site URLs.

## Selection rules

- Use `search answer` for a synthesized answer and `search sources` for URLs/results.
- Use `docs` for libraries, SDKs, repositories, directory trees, and files.
- Use `fetch content` after a URL is known; use `fetch extract` only for structured fields.
- Use `map site` for URL discovery, not page extraction or repository structure.
- Do not use removed provider commands, `search similar`, `--mode`, repository `--ref`, or Tavily Map flags.

Provider responsibility, credentials, Exa type, transport selection, and timeouts are maintainer configuration. A provider failure is final for that operation; the agent must not emulate fallback.

Default to JSON for structured results and content format for long bodies. Treat `config_error` as a maintainer issue and use `doctor`/`diagnose` only when troubleshooting is requested.
