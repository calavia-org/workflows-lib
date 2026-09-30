# PR Check and Auto-Bump Workflow

Validates PRs follow conventional commit format and automatically bumps version files based on semantic versioning.

## Features

- **Conventional commit parsing** — Analyzes PR commits or PR title for `fix:`, `feat:`, `BREAKING CHANGE:`
- **Target branch validation** — Ensures PRs target allowed branches (`main`, `release/*` by default)
- **Optional branch name validation** — Configurable regex for branch naming conventions
- **Technology auto-detection** — Supports Ansible, Node.js, Python, Rust, Generic version files
- **Maintenance releases** — Bumps based on tags from target branch (supports `release/*` branches)
- **Duplicate protection** — Skips if last commit was already a version bump

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `allowed-branch-pattern` | Regex for branch names. Set empty to disable | No | `^(major\|feat\|fix\|doc)/.+` |
| `allowed-target-branches` | Allowed target branches | No | `main,release/*` |
| `version-file` | Path to version file, or `auto` for detection | No | `auto` |
| `no-bump-branch-pattern` | Regex for branches that skip the bump. Leave empty to bump every allowed branch | No | `""` |
| `base-version-source` | `tag` derives the base from the highest release tag; `file` reads it from `version-file`. `file` requires an explicit `version-file` | No | `tag` |
| `fail-on-invalid-branch` | Fail if branch name doesn't match pattern | No | `false` |
| `require-conventional-commits` | Fail if no conventional commits found | No | `true` |

## Outputs

This workflow commits version bumps directly to the PR branch. It outputs:
- Bumped version file (detected or specified)
- Version bump commit on PR branch

## Supported Version Files

| Technology | File | Detection Priority |
|------------|------|-------------------|
| Ansible | `galaxy.yml` | 1 |
| Node.js | `package.json` | 2 |
| Python | `pyproject.toml` | 3 |
| Python | `setup.py` | 4 |
| Rust | `Cargo.toml` | 5 |
| Generic | `VERSION` | 6 |
| Generic | `version.txt` | 7 |

## Conventional Commit Format

The workflow uses conventional commits to determine version bump type:

| Commit Type | Bump | Example |
|-------------|------|---------|
| `fix:` | Patch | `fix: resolve timeout issue` |
| `feat:` | Minor | `feat: add new role` |
| `feat!:` | Major | `feat!: redesign API` |
| `BREAKING CHANGE:` | Major | `BREAKING CHANGE: remove old module` |
| `chore:`, `docs:`, etc. | Patch | `chore: update dependencies` |

For squash merge workflows, the PR title is checked as fallback.

## Usage Example

```yaml
# .github/workflows/pr-check-and-bump.yml in consumer repo
name: PR Check and Auto-Bump

on:
  pull_request:
    types: [opened, edited, reopened, synchronize]

jobs:
  pr-check-and-bump:
    uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v1
    with:
      allowed-branch-pattern: ""
      allowed-target-branches: "main,release/*"
      version-file: "auto"
      fail-on-invalid-branch: false
      require-conventional-commits: true
    secrets:
      github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Required Repository Settings

For the conventional commit detection to work reliably with squash merges:

1. **Settings → Branches → Branch protection rules**
2. For `main` and `release/*`:
   - ✅ **Require linear history** (no merge commits)
   - ✅ **Allow squash merging**
   - ❌ **Allow merge commits** (disable)
   - ❌ **Allow rebase merging** (disable)

## How It Works

1. **Checkout PR branch** with full history
2. **Validate branch name** (if configured)
3. **Validate target branch** against allowed list
4. **Parse conventional commits** in PR commits or PR title
5. **Derive base version** — from the highest release tag on the target branch
   (`base-version-source: tag`), or from `version-file` (`base-version-source: file`)
6. **Bump version** using `bump-version-action`
7. **Commit and push** version bump to PR branch (if not already bumped)

Prerelease tags are never used as a base, and a bump that does not move the
version forward is refused.

> **Prefer `file` when the version file is published as-is** (e.g. an Ansible
> Galaxy collection). A tag only moves when a release is cut, so two PRs merging
> inside one release window both derive the same base and the second produces an
> empty diff — the version silently does not advance.

## Dependencies

- [`calavia-org/bump-version-action`](https://github.com/calavia-org/bump-version-action) — Technology-agnostic version bumping
