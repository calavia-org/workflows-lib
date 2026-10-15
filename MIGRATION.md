# Migration Guide

This guide covers the major breaking release of the reusable workflow library.

Two things change for consumers:

1. Every public reusable workflow moves to the `reusable-` prefix.
2. The CI workflow's merge gate is renamed from `Test` to `Gate`.

Update the `uses:` references and the branch-protection required checks in every
repository that consumes these workflows. The repository-internal `self-*`
entrypoints are implementation detail and are not documented here.

## Rename workflow references

Update the file name in every `uses:` reference:

| Previous path | New path |
|---------------|----------|
| `.github/workflows/pr-check-and-test.yml` | `.github/workflows/reusable-ci.yml` |
| `.github/workflows/pr-check-and-bump.yml` | `.github/workflows/reusable-version-bump.yml` |
| `.github/workflows/release-artifacts.yml` | `.github/workflows/reusable-release-artifacts.yml` |
| `.github/workflows/auto-merge-dependabot.yml` | `.github/workflows/reusable-auto-merge-dependabot.yml` |

<!-- doc-ref-test: skip — the new paths resolve only after the major release publishes the tags that carry them -->
```yaml
jobs:
  ci:
    uses: calavia-org/workflows-lib/.github/workflows/reusable-ci.yml@v1
    secrets:
      github-token: ${{ secrets.GITHUB_TOKEN }}
```

Only the path in the `uses:` line changes: inputs, outputs, and every inner job
name other than the merge gate are unchanged.

## Update the required status check

The final job of `reusable-ci.yml` (job id `report`) is the merge gate. Its
display name changed from `Test` to `Gate`, which changes the status-check
context GitHub reports:

| Previous context | New context |
|------------------|-------------|
| `<caller-job> / Test` | `<caller-job> / Gate` |

`<caller-job>` is the name of the job that calls the reusable workflow in your
repository. In each consuming repository, update the branch protection rule:

1. Open **Settings** → **Branches** → the rule for `main`.
2. Under **Require status checks to pass**, remove `<caller-job> / Test` and add
   `<caller-job> / Gate`.

The gate's behavior is unchanged: it still runs with `always()` and fails
whenever any prerequisite job did not pass, so it can never report green on a
red pipeline.

## Removed workflows and actions

These are no longer published. Remove any reference to them:

| Removed | Replacement |
|---------|-------------|
| `.github/workflows/pr-check-github-action.yml` | none — use `reusable-ci.yml` |
| `.github/workflows/release-github.yml` | none — folded into `reusable-release-artifacts.yml` |
| `.github/actions/run-tox` | none — the tox matrix was removed |

The `self-bump.yml` and `self-validate.yml` workflows were repository-internal
and were never part of the consumer API.

## What did not change

- `VERSION` remains the single source of truth for the repository's version.
- The version-bump rules are unchanged (`fix:` patch, `feat:` minor, breaking
  change major).
- Pinning guidance is unchanged: `@v1` tracks the latest major release for
  development, `@vX.Y.Z` pins an exact release.
