# Release Guide

`VERSION` is the source of truth for this repository's version. It is written
only by `bump-version`, and the release workflow only reads it.

## How It Works

1. A PR is opened. `.github/workflows/pr.yml` calls the
   `version-bump.yml` contract, which reads `VERSION`, applies the bump, and
   pushes a `chore: bump version` commit to the branch.
2. When the PR merges to `main`, `.github/workflows/release.yml` triggers.
3. It reads `VERSION` and compares it against the latest tag. If they match,
   there is nothing to release and the job stops — idempotence follows from the
   version file, not from guessing at commit types.
4. Otherwise the release job creates the tag (`vX.Y.Z`), updates the floating
   major tag, and creates a GitHub Release.

The version is never derived at release time. Conventional commits decide the
*bump type* inside `version-bump.yml`; the resulting number always comes
from the file, so a release can never disagree with the version consumers read.

## Version Bump Rules

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `fix:` | Patch | `1.0.0` → `1.0.1` |
| `feat:` | Minor | `1.0.0` → `1.1.0` |
| `feat!:` or `BREAKING CHANGE:` | Major | `1.0.0` → `2.0.0` |

Branches matching `^(chore|docs|ci|test|refactor|perf|style)/` run the checks but
skip the bump. `fix/` and `feat/` deliberately stay out of that pattern: a merged
security fix still needs a patch release.

## Consumer Versioning

Repositories consuming these workflows should reference version tags:

<!-- doc-ref-test: skip — version-bump.yml is introduced by the rename in this PR; the references become valid once the release tags are moved to the commit that contains the new file. -->
```yaml
# Floating major version (recommended)
uses: calavia-org/workflows-lib/.github/workflows/version-bump.yml@v0

# Specific version (for reproducibility)
uses: calavia-org/workflows-lib/.github/workflows/version-bump.yml@v0.0.2
```

## Breaking Changes

Breaking changes trigger a major version bump. Consumers must manually update their references:

<!-- doc-ref-test: skip — hypothetical before/after transition, so these majors are intentionally unpublished -->
```yaml
# Before breaking change
uses: calavia-org/workflows-lib/.github/workflows/version-bump.yml@v1

# After breaking change
uses: calavia-org/workflows-lib/.github/workflows/version-bump.yml@v2
```

## Emergency Manual Release

If the automated workflow fails. `VERSION` still has to move first: the release
workflow compares it against the latest tag, so tagging without updating it would
leave the repository permanently one release behind and re-trigger a release on
every subsequent push.

```bash
git checkout main
git pull origin main

# 1. Move the source of truth first, via a PR so the bump is reviewed
echo "1.1.0" > VERSION

# 2. Then cut the tag for that exact version
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0

# 3. Update floating major tag (atomic: never leaves the tag missing)
git tag -f v0 v1.1.0
git push origin v0 --force
```

> The floating major tag is force-moved in a single step. Do not delete it first:
> a delete-then-repush sequence leaves a window where consumers pinning `@v0`
> resolve to nothing and the workflow reference fails to load.

> Never tag a version that `VERSION` does not contain. The release workflow
> refuses to run on a `VERSION` that is not a clean `X.Y.Z`, and it will attempt
> a release again on the next push until the two agree.
