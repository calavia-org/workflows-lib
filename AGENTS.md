# PROJECT KNOWLEDGE BASE

**Generated:** 2026-10-07
**Commit:** dad8dbf
**Branch:** docs/nested-agents-md

## OVERVIEW

`calavia-org/workflows-lib` — reusable GitHub Actions workflows (`workflow_call`) and the composite actions behind them, consumed org-wide via `@v0` / `@vX.Y.Z` tags. No application code: YAML contracts + inline bash + Python invariant tests.

## STRUCTURE

```
workflows-lib/
├── .github/workflows/   # the public reusable workflows + internal self-* (see its AGENTS.md)
├── .github/actions/     # 21 composite actions, internal implementation (see its AGENTS.md)
├── tests/               # Python invariant suites, wired into pre-commit (see its AGENTS.md)
├── docs/                # per-workflow consumer docs (inputs/outputs/usage)
├── VERSION              # bare X.Y.Z; written ONLY by bump-version
├── README.md            # consumer-facing: workflow table, usage, pinning guidance
└── RELEASE.md           # release mechanics, bump rules, emergency manual release
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add/change a reusable workflow | `.github/workflows/` | needs `docs/<name>.md` + README row |
| Change build/publish/sign logic | `.github/actions/<domain>-*` | inline bash in `action.yml` |
| Fix version/release behavior | `.github/actions/bump-version`, `release-github` | VERSION is the only authority |
| Guard an invariant | `tests/<name>.py` + `.pre-commit-config.yaml` | hook `files:` regex scopes the trigger |
| Consumer usage docs | `docs/`, `README.md` | documented `@<ref>` must be a published tag |

## CODE MAP

No LSP covers YAML workflows (Python LSP not installed); map derived from structural grep. Public contracts (the "exports" of this repo):

| Contract | Jobs | Key inputs | Outputs |
|----------|------|------------|---------|
| `pr-check-and-bump.yml` | check-pr, auto-bump-version | version-file, base-version-source, branch patterns | bump_type, should_bump, has_conventional, branch_valid, target_valid |
| `pr-check-and-test.yml` | detect, pre-commit, build, unit, package, integration, pre-release, report | 40+ (tech, phases, caching, notifications) | none (PR comments/checks) |
| `release-artifacts.yml` | 13 (detect→test→build→sign→publish→rollback) | 30+ (artifacts, targets, signing) | none |
| `release-github.yml` | release | version (required), files, draft, skip-release-types | version, tag, release-url, major-tag, skipped |
| `pr-check-github-action.yml` | detect, validate, lint, test | validate-action, run-lint, run-test | none |
| `auto-merge-dependabot.yml` | auto-merge | merge-method | none |

Most-referenced actions: `run-tests` (4 call sites), `detect-artifacts` (2), everything else 1. Internal callers reach contracts via `uses: $/...`.

## CONVENTIONS

- MINIMIZE CODE in this repo: every line carries a test obligation. Code that is absolutely needed ships with its tests in the same change, and those tests run in this repo's own PR checks (pre-commit hooks via pre-commit.ci, or a CI workflow for suites needing git history) — untested code does not merge.
- Consumers pin `@v0` (floating, dev) or `@vX.Y.Z` (reproducible); internal references use `$/` only.
- `VERSION` is written only by `bump-version` (via `pr-check-and-bump.yml`); `release.yml` reads it and compares to the latest tag — idempotence comes from the file, not commit-type guessing.
- Bump rules: `fix:` patch, `feat:` minor, `feat!:`/`BREAKING CHANGE:` major; `chore|docs|ci|test|refactor|perf|style/` branches check but skip the bump.
- Floating major tag `v0` is force-moved atomically after each release — never delete-then-repush.
- Org rules (branch naming, conventional commits, PR-only, squash) live in the org-level AGENTS.md at `~/Development/Github/AGENTS.md` and are not repeated here.

## ANTI-PATTERNS (THIS PROJECT)

- Editing `VERSION` by hand, or tagging a version `VERSION` does not contain.
- `@v0`/`@main` for internal workflow/action references (ratchet — see `.github/workflows/AGENTS.md`).
- Documenting a consumer `@<ref>` before that ref is released (`tests/doc-refs.py` fails).
- Reintroducing a regression pinned by `tests/` — see its AGENTS.md anti-patterns list.

## UNIQUE STYLES

- Invariants are executable: `tests/*.py` extract the shipped shell step from workflow YAML and replay it; comments in workflows/actions explain WHY (ratchet, single authority, tag atomicity) — keep those comments when editing.
- `.github/actionlint.yaml` suppresses exactly two errors for the `$/` self-reference syntax (actionlint predates the feature); do not broaden the ignore rules.

## COMMANDS

```bash
pre-commit run --all-files     # actionlint + 8 Python invariant suites
python3 tests/<name>.py        # run one suite (needs pyyaml)
python3 tests/doc-refs.py      # needs full tag history: git fetch --tags first
```

## NOTES

- `.omo/` holds agent scratch (evidence, notepads) — not product code; ignore when documenting.
- Dependabot: github-actions ecosystem only, weekly, grouped; auto-merged only when tied to an open security advisory.
