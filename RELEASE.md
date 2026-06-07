# Release Guide

This repository uses an **automated release workflow** that creates semantic version tags from conventional commits.

## How It Works

When a PR is merged to `main`:

1. The release workflow (`.github/workflows/release.yml`) triggers
2. It parses the conventional commit message
3. Creates a semantic version tag (`vX.Y.Z`)
4. Updates the floating major tag (`v1`, `v2`, etc.)
5. Creates a GitHub Release with auto-generated notes

## Version Bump Rules

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `fix:` | Patch | `v1.0.0` → `v1.0.1` |
| `feat:` | Minor | `v1.0.0` → `v1.1.0` |
| `feat!:` or `BREAKING CHANGE:` | Major | `v1.0.0` → `v2.0.0` |

## Consumer Versioning

Repositories consuming these workflows should reference version tags:

```yaml
# Floating major version (recommended)
uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v1

# Specific version (for reproducibility)
uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v1.0.0
```

## Breaking Changes

Breaking changes trigger a major version bump. Consumers must manually update their references:

```yaml
# Before breaking change
uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v1

# After breaking change
uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v2
```

## Emergency Manual Release

If the automated workflow fails:

```bash
git checkout main
git pull origin main
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0

# Update floating major tag
git tag -d v1
git push origin :refs/tags/v1
git tag -a v1 -m "Update v1 to v1.1.0"
git push origin v1
```
