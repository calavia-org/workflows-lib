# Release Guide: Workflows Library

This document describes the release process for the `workflows-lib` repository.

## What This Repository Is

A library of **reusable GitHub Actions workflows** (`workflow_call`) shared across the `calavia-org` organization.

This repository is designed to grow. Currently it hosts:
- `pr-check-and-bump.yml` — Validates PRs using conventional commits and auto-bumps versions

Future workflows may include:
- Container build and publish pipelines
- Terraform infrastructure automation
- Security scanning workflows
- Documentation generation workflows

## Current Workflows

### `pr-check-and-bump.yml`

Validates PRs follow conventional commit format and automatically bumps version files based on semantic versioning.

**Features:**
- Conventional commit parsing (`fix:`, `feat:`, `BREAKING CHANGE:`)
- Target branch validation (`main`, `release/*`)
- Technology auto-detection (Ansible, Node.js, Python, Rust, Generic)
- Supports maintenance releases from any target branch

**Dependencies:**
- [`calavia-org/bump-version-action`](https://github.com/calavia-org/bump-version-action) — Composite action for technology-agnostic version bumping

## Release Process (Automated)

This repository uses an **automated release workflow** (`.github/workflows/release.yml`) that:
1. Creates semantic version tags from conventional commits on push to `main`
2. Updates the floating major version tag (`v1`, `v2`, etc.)
3. Creates GitHub Releases with auto-generated notes

**No manual tagging required.**

### How It Works

When a PR is merged to `main` with a conventional commit message:
- `fix:` → patch bump (e.g., `v1.0.0` → `v1.0.1`)
- `feat:` → minor bump (e.g., `v1.0.0` → `v1.1.0`)
- `feat!:` or `BREAKING CHANGE:` → major bump (e.g., `v1.0.0` → `v2.0.0`)

### Versioning Strategy

| Version | Meaning | Consumer Impact |
|---------|---------|----------------|
| `v1.0.0` | Initial release | Pin to specific version |
| `v1.1.0` | New workflow or feature | Consumers using `@v1` get it automatically |
| `v1.1.1` | Bug fix | Consumers using `@v1` get it automatically |
| `v2.0.0` | Breaking change (input rename, removed workflow) | Consumers must manually update from `@v1` to `@v2` |

## What Consumers Reference

```yaml
# Option 1: Floating major version (recommended)
uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v1

# Option 2: Specific version (for reproducibility)
uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v1.0.0

# Option 3: Branch (not recommended for production)
uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@main
```

## Post-Release Verification

After the automated workflow runs:
1. Check that the new tag appears in [releases](https://github.com/calavia-org/workflows-lib/releases)
2. Verify the floating major tag (`v1`) points to the latest release
3. Test with a PR in a consumer repo to confirm the workflow still works

## Breaking Changes Policy

When introducing breaking changes:
1. Use `BREAKING CHANGE:` in commit message or `feat!:` prefix → triggers major version bump
2. Update `MIGRATION.md` in this repo with migration instructions
3. Notify consumer repositories via issues or PRs
4. Consumers will need to update their references from `@v1` to `@v2`

## Manual Release (Emergency Only)

If the automated workflow fails, you can manually create a tag:

```bash
git checkout main
git pull origin main
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0
```

Then update the floating major tag:
```bash
git tag -d v1
git push origin :refs/tags/v1
git tag -a v1 -m "Update v1 to v1.1.0"
git push origin v1
```

---

*For the release process of the action consumed by this workflow, see:*
- [`bump-version-action/RELEASE.md`](https://github.com/calavia-org/bump-version-action/blob/main/RELEASE.md)

*For the release process of the consumer collection, see:*
- [`ansible-collection-setup/RELEASE.md`](https://github.com/calavia-org/ansible-collection-setup/blob/main/RELEASE.md)
