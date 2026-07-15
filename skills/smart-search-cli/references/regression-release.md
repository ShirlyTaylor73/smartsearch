# Regression and Release

Maintainers run `smart-search dev regression`, relevant pytest suites, `npm test`, and verify that the public and packaged skill directories are byte-identical before release.

## Release Lanes

- Stable releases use `vX.Y.Z` tags and npm dist-tag `latest`.
- Test releases use `<package.json version>-beta.N` and npm dist-tag `next`.
- Stable bump commits use `chore(release): bump version to X.Y.Z`.
- Stable release notes live at `.github/releases/vX.Y.Z.md`.
- Historical backfills use `workflow_dispatch` with an explicit `target_ref`.
- npm versions are immutable; published versions cannot be renamed in place.

## Release Closeout Lessons

- If GitHub release creation fails after npm succeeds, keep the npm package and create the prerelease with authenticated `gh release create ... --prerelease --latest=false`.
- Treat npm `E409` during concurrent backfills as a registry concurrency issue and retry serially after checking registry state.
- Finish with a diff-style gap check between expected npm beta versions and GitHub prereleases.
- Verify the exact package with `mise use -g`, then run `smart-search --version`, `smart-search dev regression`, and `smart-search diagnose smoke --mode mock --format json`.
- During the compatibility window, `smart-search smoke --mock --format json` should emit a migration hint and forward to the new diagnose command.
- Verify the Windows npm/mise wrapper is emitting UTF-8 JSON by piping a non-ASCII JSON query such as `smart-search search answer "今天有哪些更新" --format json | ConvertFrom-Json`.
