# Workflows Library

Reusable GitHub Actions workflows for the `calavia-org` organization.

## Available Workflows

| Workflow | Purpose | Status |
|----------|---------|--------|
| [`pr-check-and-bump.yml`](.github/workflows/pr-check-and-bump.yml) | Validates conventional commits and auto-bumps versions | Active |

## Planned Workflows

This repository is designed to grow. Future additions may include:
- Container build and publish pipelines
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
