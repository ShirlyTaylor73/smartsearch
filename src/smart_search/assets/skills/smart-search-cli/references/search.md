# Web search

## `search answer`

Synthesize a current web answer with supporting sources.

```bash
smart-search search answer QUERY [--timeout SECONDS] [COMMON_FLAGS]
```

| Argument | Meaning |
|---|---|
| `QUERY` | Required question or search request. |
| `--timeout SECONDS` | Positive floating-point timeout. Default: `90`. |

Example:

```bash
smart-search search answer "What changed in Python packaging this month?" --format json
```

## `search sources`

Return relevant source results for a query.

```bash
smart-search search sources QUERY [OPTIONS] [COMMON_FLAGS]
```

| Argument | Meaning |
|---|---|
| `QUERY` | Required search query. |
| `--limit N` | Maximum result count; integer at least `1`. Default: `5`. |
| `--start-published-date DATE` | Keep results published on or after an ISO 8601 date or datetime. |
| `--include-domains DOMAIN...` | Restrict results to one or more domains. |
| `--exclude-domains DOMAIN...` | Exclude one or more domains. |
| `--category CATEGORY` | Restrict results to a supported category. |
| `--include-text` | Include retrieved page text; output can be large. |
| `--include-highlights` | Include query-relevant excerpts. |

Examples:

```bash
smart-search search sources "Python 3.14 packaging changes" --include-domains python.org --limit 5
smart-search search sources "database security advisory" --start-published-date 2026-07-01 --include-highlights
```

Read a selected result with `smart-search fetch content URL --format content`.
