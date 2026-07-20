# Regression and Release

Maintainers run `smart-search dev regression`, relevant pytest suites,
`npm test`, and verify that the public and packaged skill directories are
byte-identical before release.

## Release Lanes

- The fork-owned package is `@shirlytaylor73/smart-search`.
- Beta releases are started manually with `workflow_dispatch`, an exact
  `0.2.0-beta.N` version, and npm dist-tag `next`.
- Stable `v0.2.0` and later `vX.Y.Z` Git tags publish npm dist-tag
  `latest`.
- GitHub Actions authenticates with the repository secret `NPM_TOKEN` and
  publishes with npm provenance.
- Stable release notes live at `.github/releases/vX.Y.Z.md`.
- npm versions are immutable; published versions cannot be renamed in place.

## Release Verification

- Confirm package metadata and tags with
  `npm view @shirlytaylor73/smart-search --json`.
- Install the exact beta or stable package and run
  `smart-search --version`, `smart-search dev regression`, and
  `smart-search diagnose smoke --mode mock --format json`.
- Verify the Windows npm/mise wrapper emits UTF-8 JSON with a non-ASCII query
  piped through `ConvertFrom-Json`.

