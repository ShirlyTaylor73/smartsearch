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
smart-search fetch extract URL [--schema SCHEMA] [--max-length N] [COMMON_FLAGS]
```

| Argument | Meaning |
|---|---|
| `URL` | Required HTTP or HTTPS URL. |
| `--schema SCHEMA` | Optional JSON object describing the desired result. Omit it for automatic structured extraction. In a shell, wrap JSON in single quotes. |
| `--max-length N` | Maximum `raw_evidence` length; integer at least `0`. Default: `20000`. Structured `data` is not truncated. |

Example:

```bash
smart-search fetch extract https://example.com/product \
  --schema '{"type":"object","properties":{"name":{"type":"string"},"price":{"type":"number"}}}' \
  --format json
```
