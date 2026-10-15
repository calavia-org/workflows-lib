# .github/workflows/

> **MANDATORY READ**: This repository is governed by [`~/Development/Github/AGENTS.md`](../../../AGENTS.md) (organization-wide rules). Per-repo rules below provide project-specific details but **cannot override** organization rules.

## OVERVIEW

The product: 4 public reusable workflows (`workflow_call`) consumed org-wide via `@v0`, plus 2 internal workflows (`pr.yml`, `release.yml`) that run this repo's own PR checks, versioning, and release.

## WHERE TO LOOK

| Workflow | Role |
|----------|------|
| `version-bump.yml` | PUBLIC: conventional-commit validation + version-file bump (outputs `bump_type`, `should_bump`, ...) |
| `pr-check-and-test.yml` | PUBLIC: unified PR pipeline, tech auto-detect, `Test` gate, optional pre-release, built-in SAST/secret/misconfig/dependency scanning |
| `release-artifacts.yml` | PUBLIC: multi-target release — binary/docker/EE/helm, signing, publish, rollback |
| `auto-merge-dependabot.yml` | PUBLIC: auto-merge Dependabot PRs tied to OPEN security advisories |
| `pr.yml` | INTERNAL: on PR, runs `version-bump.yml` + `pr-check-and-test.yml` against this repo and verifies documented refs resolve to published tags |
| `release.yml` | INTERNAL: on push to main, reads `VERSION`, creates the tag and GitHub Release |

## CONVENTIONS

- Public API = `workflow_call` workflows only. Composite actions in `../actions/` are internal implementation, called via `uses: $/.github/actions/<name>`.
- Internal callers reference local contracts via `uses: $/...`, NEVER `@v0`/`@main` — the floating tag lags the contract that produced it, so a fix in the contract could not cut its own release (ratchet).
- Explicit `permissions:` on every workflow/job; baseline `contents: read`, write scopes only on jobs that push. Secrets passed one by one — never `secrets: inherit`.
- kebab-case for files, jobs, and inputs. Runner default `ubuntu-24.04`, overridable via `runner-label` input. Timeouts: detect ~5m, test/build ~30m, release ~60m.
- PR workflows: `concurrency: ${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true`; checkout with `persist-credentials: false`. Release workflows: no concurrency (sequential by design), checkout with `fetch-depth: 0`.
- Gate jobs run with `if: always()` and derive from `needs.*.result`; required status checks must never depend on optional features (e.g. `report-enabled`).
- Adding a public workflow: `workflow_call` trigger + `docs/<name>.md` + README table row + test in a consumer repo before release.

## ANTI-PATTERNS

- Deriving a version inside a workflow — `VERSION`/`bump-version` is the single authority; `release.yml` only reads the file and compares it to the latest tag.
- Referencing internal contracts at `@v0` or `@main` (ratchet) — use `$/`.
- `secrets: inherit`, implicit permissions, or write scopes on read-only jobs.
- `fetch-depth: 1` on anything that inspects tags (release, doc-refs).
- Exposing composite actions as public consumer API.
