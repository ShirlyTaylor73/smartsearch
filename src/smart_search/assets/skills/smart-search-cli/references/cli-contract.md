# CLI Contract

Public operations are `search answer|sources`, `docs resolve|search|tree|read`, `fetch content|extract`, and `map site`.

Every result contains `ok`, `capability`, `operation`, `content`, `sources`, and `elapsed_ms`. Operation data uses `results`, `candidates`, `entries`, `data`, or `raw_evidence`. Failures add `error_type` and `error`; provider metadata is debug-only.
