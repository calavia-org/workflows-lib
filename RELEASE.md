# Release Guide: Workflows Library

This document describes how to release new versions of the `workflows-lib` repository.

## What This Repository Is

A library of **reusable GitHub Actions workflows** (`workflow_call`) shared across the `calavia-org` organization.

Current workflows:
- `pr-check-and-bump.yml` — Validates PR branch names and auto-bumps versions
- `build-container.yml` — Builds and pushes container images

## Who Uses These Workflows

| Consumer | Repository | Workflow Used |
|----------|------------|---------------|
| Ansible Collection | [`calavia-org/ansible-collection-setup`](https://github.com/calavia-org/ansible-collection-setup) | `pr-check-and-bump.yml` |
| Base Template | [`calavia-org/base-template`](https://github.com/calavia-org/base-template) | Can use any workflow |

## Dependencies

| Dependency | Repository | Purpose |
|------------|------------|---------|
| Version bumping | [`calavia-org/bump-version-action`](https://github.com/calavia-org/bump-version-action) | Composite action used inside `pr-check-and-bump.yml` |

## Release Steps

### 1. Merge Changes to `main`

```bash
git checkout main
git pull origin main
```

### 2. Create a Semantic Version Tag

```bash
# For a new workflow or feature
git tag -a v1.1.0 -m "Release v1.1.0: add new reusable workflow"

# For a fix
git tag -a v1.0.1 -m "Release v1.0.1: fix pr-check-and-bump condition"

# For breaking changes
git tag -a v2.0.0 -m "Release v2.0.0: rename workflow inputs"
```

### 3. Push the Tag

```bash
git push origin v1.1.0
```

### 4. Update the Floating Major Version Tag

```bash
# Delete old v1 tag locally and remotely
git tag -d v1
git push origin :refs/tags/v1

# Recreate v1 pointing to the new release
git tag -a v1 -m "Update v1 to v1.1.0"
git push origin v1
```

This allows consumers to use `@v1` and automatically get non-breaking updates.

## Versioning Strategy

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

# Option 2: Specific version
uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v1.0.0

# Option 3: Branch (not recommended for production)
uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@main
```

## Release Checklist

- [ ] All workflows validated in a test repository
- [ ] README.md updated with workflow descriptions
- [ ] Changes don't break existing consumers (or consumers are notified)
- [ ] Version tag created (`vX.Y.Z`)
- [ ] Floating major tag updated (`vX`)
- [ ] Consumer repos updated if breaking changes

## Post-Release Verification

1. Check that `calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v1` resolves to the new tag
2. Verify a consumer workflow (e.g., in `ansible-collection-setup`) still works
3. Test with a PR in a consumer repo to confirm the full flow (branch check → version bump)

## Breaking Changes Policy

When introducing breaking changes:
1. Create a new major version tag (`v2`)
2. Update `MIGRATION.md` in this repo with migration instructions
3. Notify consumer repositories via issues or PRs
4. Keep the old major version tag (`v1`) pointing to the last v1.x.x release until consumers migrate

## Automation Options

### Option A: Manual Tagging (Current)
Create tags locally and push them.

### Option B: GitHub Actions Auto-Release
Add a workflow that creates tags from conventional commits and updates the floating major tag automatically.

### Option C: Semantic Release
Use `semantic-release` with conventional commits for fully automated versioning.

---

*For the release process of the action consumed by this workflow, see:*
- [`bump-version-action/RELEASE.md`](https://github.com/calavia-org/bump-version-action/blob/main/RELEASE.md)

*For the release process of the consumer collection, see:*
- [`ansible-collection-setup/RELEASE.md`](https://github.com/calavia-org/ansible-collection-setup/blob/main/RELEASE.md)
