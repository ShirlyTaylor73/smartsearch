# CLI Contract

Public query namespaces are `search`, `docs`, `fetch`, and `map`.

Operations: `search answer|sources|similar`, `docs resolve|search|tree|read`, `fetch content|extract`, and `map site`.

All operations return `ok`, `capability`, `operation`, `content`, `sources`, and `elapsed_ms`; failures add `error_type` and `error`. Provider details are debug-only.
