# Documentation and repositories

## `docs resolve`

Resolve a library name to a documentation source id.

```bash
smart-search docs resolve NAME [QUERY] [COMMON_FLAGS]
```

- `NAME`: required library or package name.
- `QUERY`: optional context used to rank matching libraries.

## `docs search`

Search technical documentation or repository knowledge.

```bash
smart-search docs search QUERY [--source SOURCE] [COMMON_FLAGS]
```

- `QUERY`: required documentation question.
- `--source SOURCE`: documentation id beginning with `/`, or GitHub repository `owner/repo`.

For stable library documentation, resolve the id first:

```bash
smart-search docs resolve fastapi "dependency injection"
smart-search docs search "How are yield dependencies cleaned up?" --source /fastapi/fastapi
```

## `docs tree`

List repository files and directories.

```bash
smart-search docs tree REPO [--path PATH] [COMMON_FLAGS]
```

- `REPO`: required GitHub repository in `owner/repo` form.
- `--path PATH`: repository-relative directory. The default is the repository root.

## `docs read`

Read a repository file.

```bash
smart-search docs read REPO PATH [COMMON_FLAGS]
```

- `REPO`: required GitHub repository in `owner/repo` form.
- `PATH`: required repository-relative file path.

Inspect before reading when the path is unknown:

```bash
smart-search docs tree owner/repo --path src --format json
smart-search docs read owner/repo src/package/module.py --format content
```
