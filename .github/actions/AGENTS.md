# .github/actions/

## OVERVIEW

21 composite actions — the internal implementation layer behind the reusable workflows. Not public API: consumers call `../workflows/`, never these directly. Every action is one `action.yml` with inline bash; no external `.sh` files.

## WHERE TO LOOK

| Domain | Actions |
|--------|---------|
| build | `build-binary` (7 techs), `build-docker`, `build-ee` (Ansible EE via ansible-builder), `build-helm` |
| detect | `detect-technology` (11 detectors, priority picks primary), `detect-artifacts`, `detect-version` |
| publish | `publish-ghcr`, `publish-github-release`, `publish-helm`, `publish-package`, `publish-reports` |
| sign | `sign-binary` (GPG), `sign-docker` (cosign), `sign-helm` (GPG) |
| release | `bump-version` (version authority, only action with a README), `release-github` (tags + floating `v<major>`), `generate-release-notes`, `rollback-release` |
| test/setup | `run-tests` (most reused, 4 call sites), `setup-pre-commit` |

Typical chain: `detect-technology → run-tests → detect-artifacts → build-* → sign-* → publish-*`.

## CONVENTIONS

- `using: composite`; every step declares `shell: bash`; outputs via `echo "key=value" >> "$GITHUB_OUTPUT"`.
- Inputs: `required: true` with no default, or `required: false` with an explicit default. Technology inputs use the shared vocabulary `java,nodejs,go,python,rust,ansible,generic`.
- Failures: explicit `exit 1` (add `::error::` annotation before it, as `bump-version`/`release-github` do). No `set -e`.
- Artifacts: `actions/upload-artifact@v6`, `retention-days: 7`, names tech-prefixed (`binary-<tech>-<version>`).
- Runtime versions (python 3.12, node 20, go 1.22, java 21) are hardcoded in BOTH `build-binary` and `run-tests` — a version change must land in both.
- `tests/validate-actions.py` enforces the metadata contract (name/description, inputs read, outputs assigned, step-id refs resolve) as a pre-commit hook — a new action must pass it.

## ANTI-PATTERNS

- Version logic outside `bump-version` — it is the single version authority; `release-github` only consumes the version it is given.
- Docker and EE built for the same repo: they are mutually exclusive and EE wins (`detect-artifacts` enforces this; Ansible pre-releases exclude EE entirely).
- External `.sh` files or referencing these actions at `@main` from anywhere.
- Editing a step id or output name without updating the `tests/*.py` suite that extracts it (see `../../tests/AGENTS.md`).
