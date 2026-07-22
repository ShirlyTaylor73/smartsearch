# Common CLI behavior

These flags are available on every search, docs, fetch, and map operation.

| Flag | Meaning |
|---|---|
| `--format json\|markdown\|content` | Select output rendering. The default is `json`. |
| `--output PATH` | Write the rendered result to a file instead of stdout. |
| `--debug` | Include additional diagnostic metadata. |

Use `smart-search -h` or `smart-search --help` to list commands, `smart-search COMMAND --help` for the next command level, and `smart-search -v` or `smart-search --version` to print the installed version.

## Structured output

Successful JSON output includes:

- `ok`: whether the operation succeeded.
- `capability` and `operation`: the selected CLI operation.
- `content`: primary readable content when available.
- `sources`: cited or retrieved sources.
- `elapsed_ms`: elapsed time in milliseconds.

An operation may also return `results`, `candidates`, `entries`, `data`, or `raw_evidence` according to its result type.

## Errors and diagnosis

Failures return a non-zero exit code. JSON error output includes `error_type` and `error`. Re-run the matching diagnostic command, for example:

```bash
smart-search diagnose search sources
smart-search diagnose docs read
smart-search diagnose fetch extract
smart-search diagnose map site
```

Add `--debug` to the original operation when request and response metadata is needed.
