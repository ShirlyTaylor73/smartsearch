---
name: smart-search-cli
description: "CLI-first web and documentation retrieval through four provider-independent capability namespaces."
---

# Smart Search CLI

Use the local `smart-search` command. Choose an operation by task intent; never choose or manage providers.

## Query operations

- `smart-search search answer QUERY --format json`: generate a web-backed answer.
- `smart-search search sources QUERY --limit 5 --format json`: retrieve source-first web results.
- `smart-search search similar URL --limit 5 --format json`: find similar pages.
- `smart-search docs resolve NAME [QUERY] --format json`: resolve a library/documentation source.
- `smart-search docs search QUERY [--source SOURCE] --format json`: search technical docs or repository knowledge.
- `smart-search docs tree REPO [--path PATH] [--ref REF] --format json`: inspect repository structure.
- `smart-search docs read REPO PATH [--ref REF] --format content`: read a repository file.
- `smart-search fetch content URL --format content`: retrieve readable page/PDF content.
- `smart-search fetch extract URL --format json`: retrieve structured data or raw evidence.
- `smart-search map site URL --limit 50 --format json`: discover URLs and link structure within a site.

## Selection rules

- Use `search answer` for a direct current-web answer.
- Use `search sources` when the agent needs candidate URLs or filtering.
- Use `docs` for libraries, APIs, SDKs, repositories, directory trees, and files.
- Use `fetch content` after a URL is known and readable evidence is required.
- Use `fetch extract` only when structured fields/evidence are required.
- Use `map site` only for site URL discovery; it is not page extraction or repository structure.

Provider selection, credentials, ordering, feature matching, timeout, and fallback are configuration concerns and MUST NOT be managed by the agent.

## Output and errors

- Default to `--format json` for results and `--format content` for long readable bodies.
- Treat `config_error` as a maintainer configuration issue.
- Treat `capability_error` as an unsupported operation/feature combination; do not retry with provider-specific commands.
- Use `doctor` or `diagnose` only when the user explicitly asks for troubleshooting.

The calling agent owns research orchestration; future paper/vertical retrieval is handled separately.
