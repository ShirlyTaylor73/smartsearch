# Site URL exploration

## `map site`

Discover URLs within a site.

```bash
smart-search map site URL [OPTIONS] [COMMON_FLAGS]
```

| Argument | Meaning |
|---|---|
| `URL` | Required site URL. |
| `--search TEXT` | Return URLs related to the supplied text. |
| `--sitemap include\|skip\|only` | Sitemap handling. Default: `include`. |
| `--include-subdomains` | Include subdomains. This is the default. |
| `--no-include-subdomains` | Restrict discovery to the supplied host. |
| `--ignore-query-parameters` | Treat query variants as the same URL. This is the default. |
| `--no-ignore-query-parameters` | Preserve distinct query-string variants. |
| `--ignore-cache` | Request a fresh crawl instead of cached results. Default: false. |
| `--limit N` | Maximum URL count, from `1` to `100000`. Default: `5000`. |
| `--timeout SECONDS` | Positive integer timeout. Default: `150`. |
| `--location JSON` | Location object containing only `country` and/or `languages`. |

`country` is an uppercase ISO alpha-2 code. `languages` is a non-empty array of non-empty strings. Wrap the JSON object in single quotes in a shell.

Examples:

```bash
smart-search map site https://docs.example.com --search authentication --limit 100
smart-search map site https://example.com --location '{"country":"US","languages":["en"]}' --format json
```
