# Known-URL retrieval

## `fetch content`

Return readable content from a known URL.

```bash
smart-search fetch content URL [COMMON_FLAGS]
```

- `URL`: required HTTP or HTTPS URL.
- Use `--format content` when the page body is the primary result.

## `fetch extract`

Return structured data and supporting evidence from a known URL.

```bash
smart-search fetch extract URL (--schema SCHEMA | --prompt TEXT) [--max-length N] [COMMON_FLAGS]
```

| Argument | Meaning |
|---|---|
| `URL` | Required HTTP or HTTPS URL. |
| `--schema SCHEMA` | JSON object describing the desired result. In a shell, wrap JSON in single quotes. |
| `--prompt TEXT` | Natural-language extraction intent. Firecrawl infers the output structure when no schema is supplied. |
| `--max-length N` | Maximum `raw_evidence` length; integer at least `0`. Default: `20000`. Structured `data` is not truncated. |

Provide at least one of `--schema` or `--prompt`. You may combine them to constrain the structure and guide extraction.

Example:

```bash
smart-search fetch extract https://example.com/product \
  --schema '{"type":"object","properties":{"name":{"type":"string"},"price":{"type":"number"}}}' \
  --format json

smart-search fetch extract https://www.python.org/downloads/ \
  --prompt "Extract the latest stable Python 3 version" \
  --format json
```
