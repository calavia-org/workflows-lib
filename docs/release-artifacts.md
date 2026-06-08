# Release Artifacts Workflow

## Overview

The `release-artifacts.yml` workflow handles building and releasing artifacts for multiple technologies.

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
    uses: calavia-org/workflows-lib/.github/workflows/release-artifacts.yml@v0
    with:
      technology: ansible
      artifacts: binary,docker
      ansible-collection-path: collections/ansible_collections/myorg/mycollection
      is-ansible-ee: true
      ee-definition-file: execution-environment.yml
      ghcr-image-name: my-ee
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

## Artifact Dependencies

Builds execute sequentially:
```
build-binary
  └── build-docker (needs build-binary)
        └── build-helm (needs build-docker)
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
    uses: calavia-org/workflows-lib/.github/workflows/release-artifacts.yml@v0
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
    uses: calavia-org/workflows-lib/.github/workflows/release-artifacts.yml@v0
    with:
      technology: java
      artifacts: binary,docker
      publish-github-release: true
      publish-ghcr: true
      publish-package-manager: true
      package-manager: maven
      ghcr-image-name: my-app
```

## Inputs

See [`release-artifacts.yml`](.github/workflows/release-artifacts.yml) for all available inputs.
