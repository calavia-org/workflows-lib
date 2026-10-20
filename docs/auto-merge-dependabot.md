# Auto-Merge Dependabot Workflow

Enables GitHub auto-merge on Dependabot PRs **only** when the PR is linked to an
**open** security advisory (GHSA). Everything else is left for human review.

## Features

- **Security-only merging** — auto-merge is enabled only when `dependabot/fetch-metadata`
  reports an associated GHSA id with alert state `OPEN`
- **Human review preserved** — PRs without a security alert, or whose alert is
  already resolved or rejected, are logged and skipped
- **Configurable merge method** — `squash` (default), `merge`, or `rebase`

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `merge-method` | Merge method for auto-merged PRs (`squash`, `merge`, `rebase`) | No | `squash` |

## Secrets

| Secret | Description | Required |
|--------|-------------|----------|
| `github-token` | Token with `pull-requests: write`. Use `GITHUB_TOKEN` from a `pull_request_target` trigger | Yes |

## How It Works

1. Fetch Dependabot metadata (`alert-lookup: true`)
2. Log the PR classification (dependency, ecosystem, update type, GHSA, alert state)
3. If a GHSA id exists **and** the alert state is `OPEN` → run
   `gh pr merge --auto --<merge-method>`
4. Otherwise → log why the PR was skipped

## Usage Example

```yaml
# .github/workflows/auto-merge-dependabot.yml in consumer repo
name: Auto-Merge Dependabot Security PRs

# pull_request_target is required: dependabot-triggered `pull_request` runs
# receive a read-only GITHUB_TOKEN, but enabling auto-merge needs write access.
on:
  pull_request_target:
    types: [opened, reopened, synchronize]

permissions:
  pull-requests: write

jobs:
  dependabot-automerge:
    if: ${{ github.actor == 'dependabot[bot]' }}
    uses: calavia-org/workflows-lib/.github/workflows/reusable-auto-merge-dependabot.yml@v0
    with:
      merge-method: squash
    secrets:
      github-token: ${{ secrets.GITHUB_TOKEN }}
```

> **Security note**: under `pull_request_target` the workflow runs with a
> write-capable token against PR code. Keep the caller a pure metadata workflow —
> never check out or execute code from the PR.

## Required Repository Settings

1. **Settings → General → Pull Requests → ✅ Allow auto-merge**
2. Branch protection on the target branch must require status checks to pass —
   auto-merge only merges once required checks are green

## Dependencies

- [`dependabot/fetch-metadata`](https://github.com/dependabot/fetch-metadata) —
  classifies the PR and resolves the GHSA id and alert state
