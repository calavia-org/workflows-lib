# Workflows Library

Reusable GitHub Actions workflows for the `calavia-org` organization.

## Available Workflows

| Workflow | Purpose | Status |
|----------|---------|--------|
| [`pr-check-and-bump.yml`](.github/workflows/pr-check-and-bump.yml) | Validates conventional commits and auto-bumps versions | Active |
| [`pr-check-and-test.yml`](.github/workflows/pr-check-and-test.yml) | Unified PR check and test workflow with technology auto-detection | Active |
| [`release-artifacts.yml`](.github/workflows/release-artifacts.yml) | Release artifacts (binary, docker, helm) with multi-target publishing | Active |

## Technology Support

### `pr-check-and-test.yml`
- **Auto-detect**: Python, Node.js, Go, Rust, Java, Docker, Ansible, Generic
- **Phases**: Pre-commit, lint, build, test (unit, integration, e2e), package, publish
- **Reports**: Test results, coverage, PR comments
- **Docs**: See [`docs/pr-check-and-test.md`](docs/pr-check-and-test.md)

### `release-artifacts.yml`
- **Auto-detect**: Version from `galaxy.yml`, `pom.xml`, `Chart.yml`, `package.json`, etc.
- **Artifacts**: Binary, Docker, Helm (sequential builds with dependencies)
- **Publish**: GitHub Release, GHCR, package managers, Helm chart repos
- **Features**: Conventional commits release notes, optional signing, rollback on failure
- **Ansible Specific**: Collection build (`ansible-galaxy collection build`) + Execution Environment build (`ansible-builder`)
- **Docs**: See [`docs/release-artifacts.md`](docs/release-artifacts.md)

## Planned Workflows

This repository is designed to grow. Future additions may include:
- Terraform infrastructure automation
- Security scanning workflows
- Documentation generation workflows

## Dependencies

| Dependency | Repository | Purpose |
|------------|------------|---------|
| Version bumping | [`calavia-org/bump-version-action`](https://github.com/calavia-org/bump-version-action) | Composite action used inside `pr-check-and-bump.yml` |

## Usage

Reference workflows using the `uses` keyword in your repository:

```yaml
jobs:
  pr-check:
    uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v1
    secrets:
      github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Contributing

When adding new workflows:
1. Use `workflow_call` trigger for reusability
2. Create a dedicated documentation file (see `docs/pr-check-and-bump.md` as example)
3. Update this README to list the new workflow
4. Test in a consumer repository before releasing

## Release

See [RELEASE.md](RELEASE.md) for versioning and release process.
