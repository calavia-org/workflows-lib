# tests/

## OVERVIEW

Standalone Python invariant suites — no pytest, no fixtures, no shared helpers. Each script replays a shipped workflow/action behavior and fails on regression. Only dependency: `pyyaml`.

## WHERE TO LOOK

| Suite | Invariant it guards |
|-------|---------------------|
| `version-authority.py` | VERSION file is the single version authority; release gate accepts/rejects correctly |
| `bump-version-derivation.py` | Base-version derivation (tag vs file source) never rolls a release back |
| `bump-type-selection.py` | Mixed `feat`+`fix` PR resolves to minor — never downgraded to patch |
| `bump-guard-state.py` | Already-bumped detection reads PR state, not the last commit message |
| `gate-truth-table.py` | pr-check-and-test `Test` gate goes red on any red prerequisite |
| `release-github-floating-tag.py` | Floating `v<major>` tag derives from the created tag; empty tag aborts |
| `detect-technology.py` | Technology-detection vocabulary (`ansible > python > nodejs` precedence) |
| `validate-actions.py` | Every composite action's metadata resolves to real steps/outputs |
| `doc-refs.py` | Every documented `...@<ref>` resolves to a published tag (needs tag history) |

## CONVENTIONS

- Run one suite: `python3 tests/<name>.py` (calls `git`/`bash` via `subprocess`).
- All suites except `doc-refs.py` are wired as pre-commit local hooks (`language: system`, `pass_filenames: false`, `files:` regex scoped to the files each guards). `doc-refs.py` needs `fetch-depth: 0` tag history, so it is intentionally not a pre-commit hook — run it manually after `git fetch --tags`.
- Test pattern: extract the shipped shell step out of the workflow YAML by step id, substitute `${{ ... }}` expressions with literals, run it via `bash -c` against a synthetic `GITHUB_OUTPUT` and/or a temp git repo. Helpers (`step_script_by_id`, `build_repo`) are inlined per file — there is no shared module by design; keep suites self-contained.
- A change to a workflow step id or output name read by a suite must update that suite's extraction in the same commit.

## ANTI-PATTERNS (pinned by these suites — never reintroduce)

- Prerelease tag winning over a release tag as base version.
- `git describe` for base version (commit-distance semantics break on prerelease tags).
- Bump guard keyed on `git log -1` message (a review-fix push re-triggers the bump).
- Empty `custom_tag` letting github-tag-action derive the version from commit messages.
- Documenting a `@<ref>` not yet released (forward reference); the `doc-ref-test: skip` marker exists only for intentional before/after illustrations.
- Tagging a release without moving `VERSION` first (release re-triggers on every push).
