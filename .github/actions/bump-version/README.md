# Bump Version Action

A GitHub Composite Action that bumps version files across different technologies based on semantic versioning.

## Supported Technologies

| Technology | Version File |
|------------|--------------|
| Ansible | `galaxy.yml` |
| Node.js | `package.json` |
| Python | `pyproject.toml`, `setup.py` |
| Rust | `Cargo.toml` |
| Generic | `VERSION`, `version.txt` |

## Usage

```yaml
- uses: $/.github/actions/bump-version
  with:
    version-file: auto          # or explicit path like 'galaxy.yml'
    bump-type: patch            # major, minor, or patch
    current-version: '1.2.3'    # optional, will read from file if not provided
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `version-file` | Path to version file or `auto` for detection | No | `auto` |
| `bump-type` | Type of bump: `major`, `minor`, `patch` | Yes | - |
| `current-version` | Current version string | No | Read from file |

## Outputs

| Output | Description |
|--------|-------------|
| `new-version` | The new version after bumping |
| `version-file` | The detected or provided version file path |
| `technology` | The detected technology |

## Example

```yaml
jobs:
  bump:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: $/.github/actions/bump-version
        id: bump
        with:
          version-file: auto
          bump-type: minor
      - run: |
          echo "New version: ${{ steps.bump.outputs.new-version }}"
```

## How It Works

1. **Auto-detects** the technology from common version files in the repository root
2. **Reads** the current version from the detected file
3. **Applies** semantic versioning bump based on the provided `bump-type`
4. **Writes** the new version back to the file

## Release

This action uses an automated release workflow that creates semantic version tags from conventional commits on push to `main`.
