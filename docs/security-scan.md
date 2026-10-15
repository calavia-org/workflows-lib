# Security Scanning

The `ci.yml` workflow includes a built-in `security` job that runs
open-source SAST, secret, misconfiguration, and dependency-vulnerability
scanners on every pull request. Findings fail the required `Gate` check, so they
block the merge.

## Scanners

| Scanner | Tool | What it finds |
|---------|------|---------------|
| **Secrets** | [TruffleHog](https://github.com/trufflesecurity/trufflehog) | Leaked credentials in the repository and git history. |
| **SAST** | [Semgrep](https://semgrep.dev/) | Static-code security issues using community rulesets. |
| **Misconfiguration** | [Trivy](https://trivy.dev/) | Misconfigured Dockerfiles, Kubernetes manifests, Terraform, and cloud configs. |
| **Dependencies** | [OSV-Scanner](https://github.com/google/osv-scanner) | Known vulnerabilities in lockfiles and package manifests. |

Each scanner is implemented as a composite action under `.github/actions/scan-*`
and is installed at runtime from the upstream open-source release. No
third-party GitHub Actions are used, so the scanners stay inside the
organization's Actions allowlist.

## Inputs

All inputs live on `ci.yml`:

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `run-security-scans` | boolean | `true` | Master toggle for the entire `security` job. |
| `scan-secrets` | boolean | `true` | Run TruffleHog secret scanning. |
| `scan-sast` | boolean | `true` | Run Semgrep static analysis. |
| `scan-misconfig` | boolean | `true` | Run Trivy misconfiguration scanning. |
| `scan-dependencies` | boolean | `true` | Run OSV-Scanner dependency scanning. |
| `security-severity` | string | `HIGH` | Minimum severity that causes a failure (`HIGH`, `MEDIUM`, `LOW`). |
| `security-sarif-upload` | boolean | `true` | Upload SARIF reports to the GitHub Security tab. |

## Permissions

The `security` job needs `security-events: write` so the scanner actions can
upload SARIF results:

```yaml
jobs:
  ci:
    uses: calavia-org/workflows-lib/.github/workflows/reusable-ci.yml@v0
    permissions:
      contents: write
      checks: write
      pull-requests: write
      security-events: write
    secrets:
      github-token: ${{ secrets.GITHUB_TOKEN }}
```

The reusable workflow already declares the job-level permission, but the calling
job must grant it.

## Disabling scanners

To turn off the entire security job:

```yaml
with:
  run-security-scans: false
```

To disable an individual scanner while keeping the rest:

```yaml
with:
  scan-dependencies: false
```

## Reports

When `security-sarif-upload` is `true`, every scanner uploads its own SARIF
report to the GitHub Security tab with a distinct category:

- `trufflehog-secrets`
- `semgrep-sast`
- `trivy-misconfig`
- `osv-scanner-dependencies`

Findings appear under the repository's **Security → Code scanning alerts** tab.
