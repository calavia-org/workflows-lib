# Release Artifacts Workflow

## Overview

The `release-artifacts.yml` workflow handles building and releasing artifacts for multiple technologies.

## Action References

Composite actions used by this workflow are referenced remotely from external repositories, not from local paths within workflows-lib.

### Remote Reference Format

All composite actions use the format:

```text
calavia-org/workflows-lib/.github/actions/NAME@v0
```

**Required path prefix**: The `.github/actions/` segment is mandatory in the path. Short formats like `calavia-org/workflows-lib/actions/NAME@v0` will fail.

**Version tag**: `@v0` is a floating major tag that always points to the latest stable release. It is auto-updated by the `release.yml` workflow whenever a new version is tagged.

### Self-Releasing Pattern

The workflows-lib repository uses a self-releasing pattern:

1. `release.yml` watches for version bumps in source files (e.g., `galaxy.yml`, `package.json`, `VERSION`)
2. On push to `main` after a version change, `self-release.yml` calls `reusable-release-artifacts.yml` with `update-floating-major-tag: true`, which:
   - Creates a GitHub Release with the new version
   - Tags the repository (e.g., `v1.2.3`)
   - Updates the `v0` tag to point to the new release
3. Consumers referencing `@v0` automatically get the latest stable version without manual updates

This pattern ensures that consumers of `calavia-org/workflows-lib` always receive up-to-date actions when they reference `@v0`, while version-pinned references (e.g., `@v1.2.3`) remain stable for pinned consumers.

Use `update-floating-major-tag: true` when your repository ships reusable workflows or actions that consumers pin with a floating major tag such as `@v1`.

## Technology Support

### Ansible

For Ansible collections, the workflow supports two artifact types:

1. **Collection Build** (`ansible-galaxy collection build`)
   - Builds the collection tarball
   - Publishes to Ansible Galaxy

2. **Execution Environment** (`ansible-builder`)
   - Builds Docker image using `ansible-builder`
   - Publishes to GHCR
   - Uses `execution-environment.yml` definition

#### Required Inputs

```yaml
jobs:
  release:
    uses: calavia-org/workflows-lib/.github/workflows/reusable-release-artifacts.yml@v0
    with:
      technology: ansible
      artifacts: binary,docker
      ansible-collection-path: collections/ansible_collections/myorg/mycollection
      is-ansible-ee: true
      ee-definition-file: execution-environment.yml
```

#### Required Files

- `galaxy.yml` - Collection manifest with version
- `execution-environment.yml` - EE definition (for Docker build)
- `collections/ansible_collections/...` - Collection source

### Java

Supports Maven and Gradle builds:

- `mvn package -DskipTests`
- `gradle build -x test`

### Node.js

- `npm run build` / `npm pack`
- `npm publish` to registry

### Python

- `python -m build` or `poetry build`
- `twine upload` or `poetry publish`

### Go

- `go build` / `goreleaser`
- Binary release

### Rust

- `cargo build --release`
- `cargo publish`

### Docker

- Standard `docker build`
- Or `ansible-builder` for Execution Environments

### Helm

- `helm package`
- Push to chart repository

## Version Detection

The workflow auto-detects version from (in priority order):

1. `galaxy.yml` (Ansible)
2. `pom.xml` (Java)
3. `Chart.yml` (Helm)
4. `package.json` (Node.js)
5. `Cargo.toml` (Rust)
6. `pyproject.toml` (Python)
7. `setup.py` (Python)
8. `VERSION` or `version.txt` (Generic)

## Testing Before Release

When `run-tests: true` the workflow separates unit and integration testing:

- **Unit tests** run once via `test-command`.
- **Integration tests** fan out through the same `reusable-integration-matrix.yml` used by the CI workflow, so a consumer can test the same scenario × Python × ansible-core matrix during release that it already validated in PRs.

Integration matrix inputs (all optional):

| Input | Purpose |
|-------|---------|
| `integration-python-matrix` | JSON array of Python versions for integration legs |
| `integration-ansible-matrix` | JSON array of ansible-core versions (Ansible consumers) |
| `molecule-search-paths` | Comma-separated paths to discover molecule scenarios |
| `molecule-scenarios-matrix` | JSON array to override the discovered scenario matrix |
| `molecule-scenario-filter-mode` | `all` or `affected` (same semantics as CI) |
| `molecule-scenario-mapping` | Optional scenario → role/pattern mapping file |
| `molecule-affected-fallback-all` | Fall back to all scenarios when affected mode finds none |

The integration command template receives the matrix values in environment variables:

- `MATRIX_PYTHON_VERSION`
- `MATRIX_ANSIBLE_CORE`
- `MATRIX_SCENARIO`

## Artifact Dependencies

Builds execute sequentially after tests succeed:

```text
detect
  ├── unit
  ├── integration-matrix → integration
  ├── build-binary
  │     ├── build-docker
  │     │     └── build-helm
  │     └── sign-binary
  └── ...
```

## Publish Targets

- **GitHub Release** - Attach artifacts and release notes
- **GHCR** - Docker images
- **Package Manager** - npm, PyPI, Maven, Ansible Galaxy
- **Helm Chart Repo** - Chart packages

## Release Notes

Auto-generated from conventional commits:

- 🚀 Features (`feat:`)
- 🐛 Bug Fixes (`fix:`)
- 📝 Documentation (`docs:`)
- 🔧 Maintenance (`chore:`, `refactor:`, `test:`)
- 🏗️ Build (`build:`, `ci:`)
- 🛡️ Security (`security:`)
- 💥 Breaking Changes (`BREAKING CHANGE:`)

## Signing (Optional)

- **GPG** for binaries and Helm charts
- **Cosign** for Docker images
- **Notary** for Helm charts

## Rollback

On failure, the workflow can:

- Delete GitHub Release
- Delete GHCR images
- Revert package manager publish
- Notify on Slack

## Example Usage

### Ansible Collection + EE

```yaml
jobs:
  release:
    uses: calavia-org/workflows-lib/.github/workflows/reusable-release-artifacts.yml@v0
    with:
      technology: ansible
      artifacts: binary,docker
      version-source: collections/ansible_collections/myorg/mycollection/galaxy.yml
      publish-github-release: true
      publish-ghcr: true
      publish-package-manager: true
      package-manager: ansible-galaxy
      ghcr-image-name: my-ee
      is-ansible-ee: true
      ee-definition-file: execution-environment.yml
      ansible-collection-path: collections/ansible_collections/myorg/mycollection
```

### Java Application

```yaml
jobs:
  release:
    uses: calavia-org/workflows-lib/.github/workflows/reusable-release-artifacts.yml@v0
    with:
      technology: java
      artifacts: binary,docker
      publish-github-release: true
      publish-ghcr: true
      publish-package-manager: true
      package-manager: maven
      ghcr-image-name: my-app
```

## Ansible-Specific Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `ansible-collection-path` | string | `''` | Path to Ansible collection directory (e.g., `collections/ansible_collections/myorg/mycollection`) |
| `is-ansible-ee` | boolean | `false` | Build Ansible Execution Environment instead of standard Docker image |
| `ee-definition-file` | string | `'execution-environment.yml'` | Path to execution-environment.yml definition file |

When `is-ansible-ee` is `true`:

- The Docker build step uses `ansible-builder` instead of `docker build`
- The EE image is built using the specified `execution-environment.yml`
- The image is tagged with the version and pushed to GHCR

## Inputs

See [`reusable-release-artifacts.yml`](.github/workflows/reusable-release-artifacts.yml) for all available inputs.
