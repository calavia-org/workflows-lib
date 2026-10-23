# Security Scanning

The `ci.yml` workflow includes a built-in `security` job that runs
open-source SAST, secret, misconfiguration, and dependency-vulnerability
scanners on every pull request. Findings fail the required `Gate` check, so they
block the merge.

Each scanner runs as its own parallel job (a matrix leg named
`Security Scan (secrets)`, `Security Scan (sast)`, etc.) rather than as a
sequential step in a single job. Two reasons:

- **SARIF isolation.** The `upload-sarif` action scopes uploads by job
  analysis key. Sequential uploads within one job contend on that key, and
  the second upload can fail the whole job even when the scan itself found
  nothing blocking.
- **Parallelism.** Semgrep alone can take minutes; the legs run
  concurrently. `fail-fast` is deliberately `false` so a red scanner never
  cancels its siblings — every report is needed to triage the PR.

Consumers that require only the aggregated `Gate` check are unaffected by
the per-scanner job names.

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
| `security-dependency-review` | boolean | `true` | Run the pull-request-only `Dependency Review` job against the GitHub dependency graph. |
| `security-dependencies-extra-args` | string | `''` | Extra arguments appended to the OSV-Scanner CLI (for example `--no-resolve` or an `--experimental-exclude` pattern). |

## Dependency Review gate

`reusable-ci.yml` also runs a `Dependency Review` job on pull requests. It reads
the GitHub dependency graph and reports only the vulnerable dependencies a PR
introduces, so it is fast enough to run on every PR. It complements the full
OSV-Scanner scan, which resolves the entire manifest set and is the slow path.

Coverage follows the dependency graph: ecosystems or manifests that are not in
the graph are not reviewed. Set `security-dependency-review: false` to disable
the job. Use `security-dependencies-extra-args` to tune the OSV-Scanner leg, for
example `--no-resolve` to skip transitive dependency resolution.

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

## Scheduled full scans

`reusable-ci.yml` is designed as a pull-request gate. For periodic full scans of
a branch, call `reusable-security-scan.yml` from a `schedule` or
`workflow_dispatch` workflow instead. It runs the same four scanners without
technology detection or pull-request-only inputs, so it works outside a pull
request. See the README for a usage example.
