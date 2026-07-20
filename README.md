# Smart Search

`smart-search` is a CLI-first web and technical-document retrieval tool for AI agents and terminal users. Agents choose task operations; provider selection, credentials, feature matching, timeouts, and fallback remain configuration concerns.

## Install and setup

`smart-search` is implemented in Python. The npm package is an npm wrapper
that creates an isolated Python runtime and installs the bundled Python CLI.

During the 0.2.0 preview, install the fork-owned package from npm dist-tag
`next`:

```bash
npm install -g @shirlytaylor73/smart-search@next
smart-search setup
smart-search doctor --format json
```

After `v0.2.0` is published, stable installations can use
`@shirlytaylor73/smart-search@latest`.

Python source installation:

```bash
uv tool install --editable .
# or
pip install -e .
smart-search --version
```

## Four query capabilities

### search

```bash
smart-search search answer "latest AI policy updates" --format json
smart-search search sources "agentic search papers" --limit 5 --mode semantic --include-highlights --format json
smart-search search similar https://example.com/article --limit 5 --format json
```

`search sources` supports provider-independent limit, semantic/keyword/auto mode, publication date, include/exclude domains, category, text, and highlights. Providers that do not support required features are excluded automatically.

### docs

```bash
smart-search docs resolve react hooks --format json
smart-search docs search "useEffect cleanup" --format json
smart-search docs search "recent important PRs" --source owner/repo --format json
smart-search docs tree owner/repo --path src --ref main --format json
smart-search docs read owner/repo README.md --ref main --format content
```

### fetch

```bash
smart-search fetch content https://example.com/article --format content
smart-search fetch extract https://example.com/product --schema '{"type":"object"}' --format json
```

- `fetch content` returns readable text or Markdown.
- `fetch extract` returns structured `data` and optional `raw_evidence`; it never substitutes ordinary Markdown for structured output.

### map

```bash
smart-search map site https://docs.example.com \
  --instructions "find authentication and rate-limit pages" \
  --max-depth 1 \
  --max-breadth 20 \
  --limit 50 \
  --timeout 150 \
  --format json
```

`map site` discovers URLs, paths, and link structure within a site. It is not page extraction or repository structure; use `fetch content` and `docs tree` for those tasks.

## Operation/provider mapping

| Operation | Internal candidates |
|---|---|
| `search.answer` | xAI Responses, OpenAI-compatible |
| `search.sources` | Exa, Zhipu Web Search, Zhipu MCP, Tavily, Firecrawl |
| `search.similar` | Exa |
| `docs.resolve` | Context7 |
| `docs.search` | Context7, Exa, Zhipu MCP zread |
| `docs.tree` | Zhipu MCP zread |
| `docs.read` | Zhipu MCP zread |
| `fetch.content` | Tavily, Jina, Zhipu MCP Reader, Firecrawl |
| `fetch.extract` | Firecrawl structured extraction |
| `map.site` | Tavily |

Fallback stays within the same operation. `docs.tree` never falls back to Context7, and `fetch.extract` never falls back to readable Markdown.

Maintainers can configure per-operation ordering, disabled providers, timeout, and fallback through the JSON object in `SMART_SEARCH_OPERATION_CONFIG`. Agents do not manage this setting.

## Configuration and diagnostics

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

Common credentials include `XAI_API_KEY`, `OPENAI_COMPATIBLE_API_URL`, `OPENAI_COMPATIBLE_API_KEY`, `EXA_API_KEY`, `CONTEXT7_API_KEY`, `ZHIPU_API_KEY`, `ZHIPU_MCP_API_KEY`, `JINA_API_KEY`, `TAVILY_API_KEY`, and `FIRECRAWL_API_KEY`. `config list` masks secrets.

## Output and exit codes

Query operations support:

```bash
--format json|markdown|content
--output PATH
--debug
```

The public JSON envelope contains `ok`, `capability`, `operation`, `content`, `sources`, and `elapsed_ms`. Exit codes: `0` success, `2` parameter error, `3` configuration error, `4` network/capability error, and `5` runtime error.

## Migration

### npm package ownership

This repository publishes `@shirlytaylor73/smart-search`. The upstream
`@konbakuyomu/smart-search` package is a separate package and does not
receive updates from this fork. Both packages expose the same
`smart-search` executable, so uninstall the upstream package first:

```bash
npm uninstall -g @konbakuyomu/smart-search
npm install -g @shirlytaylor73/smart-search@next
smart-search -v
smart-search diagnose smoke --mode mock
```

The configuration directory does not change, so existing credentials and
`SMART_SEARCH_OPERATION_CONFIG` values remain available.

### CLI contract

Legacy provider commands are hidden during the compatibility window and map to operations, for example `exa-search` → `search sources`, `exa-similar` → `search similar`, `context7-library` → `docs resolve`, legacy `fetch` → `fetch content`, and legacy `map` → `map site`.

The experimental vertical provider and Deep Research CLI were removed. The calling agent owns research decomposition, evidence comparison, and final writing; paper and vertical retrieval will be extended separately through paper-search.

## Development

```bash
smart-search dev regression
python -m compileall -q src tests
python -m pytest tests -q
npm test
```

## Release lanes

Beta releases are started manually through `workflow_dispatch` with an
explicit `target_ref`, version such as `0.2.0-beta.1`, and npm dist-tag
`next`. Stable releases use a matching tag such as `v0.2.0` and publish
to npm dist-tag `latest`. GitHub Actions reads the repository secret
`NPM_TOKEN` and publishes with provenance.

npm versions are immutable and cannot be renamed in place. Failed beta builds
must be superseded by a new `0.2.0-beta.N` version.

Release closeout checklist:

1. Compare npm versions/dist-tags and GitHub releases before publishing.
2. If Actions cannot create a prerelease, publish with
   `create_github_release=false`, then run
   `gh release create vX.Y.Z-beta.N --target <commit> --prerelease --latest=false`.
3. Treat npm `E409` during parallel backfills as a registry concurrency
   failure and retry serially after checking whether the version exists.
4. Run a machine-readable gap check between expected npm beta versions and
   GitHub prereleases.
5. Install the selected build with
   `mise use -g "npm:@shirlytaylor73/smart-search@0.2.0-beta.1" -y --pin`,
   then verify version, regression, smoke, and a non-ASCII JSON pipe through
   PowerShell `ConvertFrom-Json`.
