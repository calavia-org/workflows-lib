# Workflows Library

Reusable GitHub Actions workflows for the `calavia-org` organization.

## Available Workflows

| Workflow | Purpose | Status |
|----------|---------|--------|
| [`pr-check-and-bump.yml`](.github/workflows/pr-check-and-bump.yml) | Validates conventional commits and auto-bumps versions | Active |
| [`pr-check-and-test.yml`](.github/workflows/pr-check-and-test.yml) | Unified PR check, test, and security scanning workflow with technology auto-detection | Active |
| [`release-artifacts.yml`](.github/workflows/release-artifacts.yml) | Release artifacts (binary, docker, helm) with multi-target publishing | Active |

## Technology Support

### `pr-check-and-test.yml`
- **Auto-detect**: Python, Node.js, Go, Rust, Java, Docker, Ansible, Generic
- **Phases**: Pre-commit, lint, build, test (unit, integration, e2e), package, publish
- **Security**: Secret scanning (TruffleHog), SAST (Semgrep), misconfiguration scanning (Trivy), dependency CVE scanning (OSV-Scanner)
- **Reports**: Test results, coverage, SARIF uploads, PR comments
- **Docs**: See [`docs/security-scan.md`](docs/security-scan.md)

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
- Release-time SBOM, provenance, and artifact vulnerability scanning
- Documentation generation workflows

## Dependencies

| Dependency | Repository | Purpose |
|------------|------------|---------|
| Version bumping | [`bump-version`](.github/actions/bump-version) | Composite action used inside `pr-check-and-bump.yml` |

## Usage

Reference workflows using the `uses` keyword in your repository:

```yaml
jobs:
  pr-check:
    uses: calavia-org/workflows-lib/.github/workflows/pr-check-and-bump.yml@v0
    secrets:
      github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Version Tags

- `v0` - Tracks latest v0.x.x release (development, moves with each release)
- `v0.0.1`, `v0.0.2`, etc. - Fixed versions for reproducibility
- When major version 1 released, pin to explicit version (e.g., `v1.0.0`)

### Development vs Production

**Development** (consumer repositories):
```yaml
uses: calavia-org/workflows-lib/.github/workflows/release-artifacts.yml@v0
```

**Production** (stable releases):
```yaml
uses: calavia-org/workflows-lib/.github/workflows/release-artifacts.yml@v0.0.2
```

## Development

This repository uses [mise](https://mise.jdx.dev/) to pin development tools. Install mise, then run commands through it so you use the pinned Python version instead of the system interpreter:

```bash
mise install
mise exec -- pip install -e ".[test]"
mise exec -- pytest
mise exec -- tox
```

The [`mise.toml`](mise.toml) file pins Python to 3.12. Do not use Python 3.9 for development or CI; `pyproject.toml` declares `requires-python = ">=3.10"` and `tox.ini` runs the matrix across 3.10, 3.11, and 3.12.

### Running tests

All invariant suites are pytest-collectable. To run the full suite:

```bash
mise exec -- pytest -v
```

To run the version matrix locally:

```bash
mise exec -- tox
```

## Contributing

When adding new workflows:
1. Use `workflow_call` trigger for reusability
2. Create a dedicated documentation file (see `docs/pr-check-and-bump.md` as example)
3. Add or extend a pytest-collectable invariant suite in `tests/`
4. Update this README to list the new workflow
5. Test in a consumer repository before releasing

## Release

See [RELEASE.md](RELEASE.md) for versioning and release process.
