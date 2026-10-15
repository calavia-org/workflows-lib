#!/usr/bin/env python3
"""Verify the internal PR caller admits Dependabot branches and still bumps them.

workflows-lib versions itself through `version-bump.yml` (see
`.github/workflows/pr.yml`). That call sets `fail-on-invalid-branch: true`,
so a branch missing from `allowed-branch-pattern` makes the whole
"Check PR and bump version" check go red — exactly what happened for
`dependabot/github_actions/...` PRs, which could then never auto-merge.

Two invariants are pinned here, both about the wiring in pr.yml:

1. `allowed-branch-pattern` accepts a real Dependabot branch, so validation
   passes instead of failing the check.
2. `no-bump-branch-pattern` does NOT match a Dependabot branch, so a merged
   security bump still cuts a patch release (a Dependabot `build(deps):` commit
   parses to `patch`).

Regression to guard: dropping `dependabot` from the allowed set silently
re-reds every Dependabot PR; adding `dependabot` to the no-bump set silently
stops security fixes from ever publishing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PR_WORKFLOW = ROOT / ".github/workflows/pr.yml"

# A real Dependabot branch name, taken from the run that exposed the bug.
DEPENDABOT_BRANCH = "dependabot/github_actions/github-actions-640176b5ab"
BUMP_JOB = "check-pr-and-bump"


def bump_with() -> dict:
    """Return the `with:` inputs of the PR caller's bump job."""
    data = yaml.safe_load(PR_WORKFLOW.read_text())
    return data["jobs"][BUMP_JOB]["with"]


def test_allowed_pattern_accepts_dependabot():
    allowed = bump_with()["allowed-branch-pattern"]
    assert re.search(allowed, DEPENDABOT_BRANCH), (
        f"pr.yml allowed-branch-pattern {allowed!r} rejects "
        f"{DEPENDABOT_BRANCH!r}; Dependabot PRs would fail branch validation"
    )
    print(f"pr.yml OK: allowed-branch-pattern admits {DEPENDABOT_BRANCH!r}")


def test_no_bump_pattern_does_not_skip_dependabot():
    no_bump = bump_with()["no-bump-branch-pattern"]
    assert not re.search(no_bump, DEPENDABOT_BRANCH), (
        f"pr.yml no-bump-branch-pattern {no_bump!r} matches "
        f"{DEPENDABOT_BRANCH!r}; a merged security bump would never publish"
    )
    print(f"pr.yml OK: no-bump-branch-pattern leaves {DEPENDABOT_BRANCH!r} to bump")


def main() -> int:
    test_allowed_pattern_accepts_dependabot()
    test_no_bump_pattern_does_not_skip_dependabot()
    print("\npr-bump-branch-pattern OK")
    return 0


def test_main():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
