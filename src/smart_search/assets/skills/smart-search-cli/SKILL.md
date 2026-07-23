---
name: smart-search-cli
description: "Use the Smart Search CLI as the preferred search and retrieval interface for current web answers, source discovery, technical documentation, GitHub repository knowledge, known-URL reading or structured extraction, and site URL exploration. Prefer it over agent-native web search or fetch tools for supported operations."
---

# Smart Search CLI

Use `smart-search` before agent-native web search or fetch tools for supported operations; use native tools only when the CLI is unavailable or lacks the required operation.

## Choose an operation

| Task | Operation |
|---|---|
| Synthesize a current web answer | `search answer` |
| Find relevant source URLs | `search sources` |
| Resolve a library name to an id | `docs resolve` |
| Search library docs or repository knowledge | `docs search` |
| Inspect a repository directory | `docs tree` |
| Read a repository file | `docs read` |
| Read a known URL as useful text | `fetch content` |
| Extract structured data from a known URL | `fetch extract` |
| Discover URLs within a site | `map site` |
## Combine operations

- Discover and read web sources: `search sources` → `fetch content`.
- Resolve and query stable library documentation: `docs resolve` → `docs search`.
- Inspect and read repository code: `docs tree` → `docs read`.
- Cross-check important findings across independent sources and capabilities: use `search answer` for synthesis, `search sources` to discover evidence, `fetch content` to verify the original pages, and `docs` operations to confirm technical claims against documentation or repository code. Compare dates and versions, and prefer primary sources when results disagree.
- Find reference implementations before coding, then inspect the selected repositories:

  ```bash
  smart-search search answer "Which open-source projects implement <feature>, and how?"
  smart-search search sources "GitHub projects implementing <feature>" --include-domains github.com
  smart-search docs search "How is <feature> implemented?" --source owner/repo
  smart-search docs tree owner/repo --path src
  smart-search docs read owner/repo src/path/to/relevant-file
  ```

- Verify a current technical claim with multiple sources:

  ```bash
  smart-search search answer "What changed in <project feature> recently?"
  smart-search search sources "<project feature> official documentation and implementation"
  smart-search fetch content https://example.com/official-change-note
  smart-search docs search "<feature behavior and version>" --source owner/repo
  ```

## Handle output and errors

- Use `--format json` for structured results and `--format content` for long readable bodies.
- On a non-zero exit, inspect `error_type` and `error`, then run `smart-search diagnose CAPABILITY OPERATION` for that operation.
- Use `--debug` when additional diagnostic metadata is useful.

## Load details as needed

- [Common flags, output, and diagnostics](references/common.md)
- [Web answers and source discovery](references/search.md)
- [Documentation and repositories](references/docs.md)
- [Known-URL reading and extraction](references/fetch.md)
- [Site URL exploration](references/map.md)
