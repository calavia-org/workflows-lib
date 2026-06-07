# Workflows Library

Reusable GitHub Actions workflows for the `calavia-org` organization.

## Current Workflows

| Workflow | Purpose | Status |
|----------|---------|--------|
| `pr-check-and-bump.yml` | Validates conventional commits and auto-bumps versions | Active |

## Planned Workflows

This repository is designed to grow. Future workflows may include:
- Container build and publish pipelines
- Terraform infrastructure automation
- Security and compliance scanning
- Documentation and changelog generation

## Using These Workflows

In your repository, reference workflows using the `uses` keyword:

```yaml
jobs:
  pr-check:
    uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v1
    secrets:
      github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Dependencies

| Dependency | Repository | Purpose |
|------------|------------|---------|
| Version bumping | [`calavia-org/bump-version-action`](https://github.com/calavia-org/bump-version-action) | Composite action used inside `pr-check-and-bump.yml` |

## Contributing

When adding new workflows:
1. Use `workflow_call` trigger for reusability
2. Document inputs, outputs, and usage in the workflow file
3. Update this README with the new workflow
4. Test in a consumer repository before releasing
