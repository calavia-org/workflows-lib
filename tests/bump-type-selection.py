#!/usr/bin/env python3
"""Verify how pr-check-and-bump.yml selects the bump type from a PR's commits.

The derivation suite proves which *base version* a bump starts from. This suite
covers the other half: which *type* that bump takes. The two are independent
decisions, and only the first was under test.

That gap is not academic. The selection loop overwrites `BUMP_TYPE` as it walks
the commit list, and the three classification branches guard their assignment
differently on purpose:

    breaking change  ->  BUMP_TYPE="major"   unconditionally, then break
    feat             ->  BUMP_TYPE="minor"   only if BUMP_TYPE != "major"
    fix              ->  BUMP_TYPE="patch"   only if BUMP_TYPE is empty
    chore/docs/...   ->  BUMP_TYPE="patch"   only if BUMP_TYPE is empty

The `fix` and `chore` branches use `[ -z "$BUMP_TYPE" ]` rather than
`[ "$BUMP_TYPE" != "major" ]`. That is load-bearing. A pull request carrying both
a `feat` and a `fix` must resolve to `minor`, because semver says a PR adding a
feature is a minor release even when it also carries fixes. Had those branches
guarded only against `major`, a later `fix` would overwrite an earlier `feat`
and the release would ship a patch instead -- silently, with no failing check.

The guard is easy to misread. It reads like the `feat` guard beside it, differs
by one character class, and a plausible "consistency" edit that unifies them
downgrades every mixed-type PR without any test going red.

The step is EXTRACTED FROM THE WORKFLOW and executed with bash against synthetic
commit lists, so this tests the shipped shell rather than a paraphrase of it. A
comment quoting the logic would not catch that edit; running it does.

Exit code 0 when every case resolves as specified, 1 otherwise.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WF = ROOT / ".github/workflows/pr-check-and-bump.yml"
BUMP_STEP_ID = "conventional"


def step_script_by_id(step_id: str) -> str:
    """Return the `run:` script of the step with this id, verbatim."""
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if step.get("id") == step_id:
                return step["run"]
    raise SystemExit(f"error: step id not found in {WF.name}: {step_id}")


def select_bump(
    commits: list[str],
    pr_title: str = "",
    require_conventional: str = "true",
) -> tuple[str | None, str]:
    """Run the workflow's selection loop over `commits`.

    Returns (bump_type, combined output). `commits` are ordered newest first,
    matching `git log`, so index 0 is the most recent commit.
    """
    script = step_script_by_id(BUMP_STEP_ID)

    # Substitute `require-conventional-commits` before the blanket expression
    # strip: the step's last rule compares it to "false", so blanking it instead
    # would leave that rule permanently false and silently drop coverage.
    script = script.replace(
        "${{ inputs.require-conventional-commits }}", require_conventional
    )
    # The step reads its commit list from git and interpolates GitHub expressions
    # into shell. Both are replaced so the real script can run outside Actions:
    # `commits` becomes a literal newline-delimited string.
    script = re.sub(r"\$\{\{[^}]*\}\}", "", script)
    script = re.sub(
        r'^(\s*)COMMITS=\$\(git log[^\n]*\n',
        lambda m: f"{m.group(1)}COMMITS=$(cat <<'__COMMITS__'\n"
        + "".join(f"{c}\n" for c in commits)
        + "__COMMITS__\n)\n",
        script,
        count=1,
        flags=re.M,
    )

    with tempfile.TemporaryDirectory() as tmp:
        out = f"{tmp}/out"
        # A git repo is still required: the step's `if:` guards and the
        # `set -euo pipefail` prologue read git state even though the loop itself
        # no longer calls git.
        repo = f"{tmp}/repo"
        subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
        for cmd in (
            ["git", "-C", repo, "config", "user.email", "t@example.com"],
            ["git", "-C", repo, "config", "user.name", "T"],
            ["git", "-C", repo, "commit", "-q", "--allow-empty", "-m", "base"],
        ):
            subprocess.run(cmd, check=True)

        full = (
            "set -uo pipefail\n"
            f"export GITHUB_OUTPUT={out}\n"
            f"export BASE_BRANCH=main\n"
            f"export PR_TITLE={pr_title!r}\n"
            f"cd {repo}\n"
            + script
        )
        proc = subprocess.run(["bash", "-c", full], capture_output=True, text=True)
        bump = _read_bump_type(out, proc.stdout + proc.stderr)

    return bump, proc.stdout + proc.stderr


def _read_bump_type(out_path: str, step_output: str) -> str | None:
    """Pull `bump_type` out of the step's GITHUB_OUTPUT.

    The step writes that key unconditionally, so a missing file means the harness
    ran wrong rather than the step declining to answer. Echoing the step's own
    output keeps that case diagnosable instead of silently reading as "no bump".
    """
    try:
        lines = pathlib.Path(out_path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print(f"error: step wrote no GITHUB_OUTPUT; its output was:\n{step_output}")
        return None
    for line in lines:
        if line.startswith("bump_type="):
            return line.split("=", 1)[1].strip()
    print(f"error: bump_type absent from GITHUB_OUTPUT; step output:\n{step_output}")
    return None


# (commits newest-first, pr_title, require_conventional, expected, why)
CASES = [
    ([], "", "true", "", "no commits and no title resolves to nothing"),
    (
        [],
        "",
        "false",
        "patch",
        "no commits at all still defaults to patch when the requirement is off",
    ),
    (["feat(api): add thing"], "", "true", "minor", "a lone feature is a minor bump"),
    (["fix(api): repair thing"], "", "true", "patch", "a lone fix is a patch bump"),
    (["chore: tidy deps"], "", "true", "patch", "chore is conventional and bumps patch"),
    (["docs: correct prose"], "", "true", "patch", "docs is conventional and bumps patch"),
    (["refactor: tidy internals"], "", "true", "patch", "refactor is conventional"),
    (["test: add cases"], "", "true", "patch", "test is conventional"),
    (["ci: adjust workflow"], "", "true", "patch", "ci is conventional"),
    (
        ["fix(a): patch", "feat(b): feature"],
        "",
        "true",
        "minor",
        "a fix seen before a feat still resolves to minor, because feat wins",
    ),
    (
        ["feat(b): feature", "fix(a): patch"],
        "",
        "true",
        "minor",
        "REGRESSION: a fix seen after a feat must not downgrade the bump to patch",
    ),
    (
        ["chore: tidy", "feat(b): feature"],
        "",
        "true",
        "minor",
        "a chore seen before a feat still resolves to minor, because feat wins",
    ),
    (
        ["feat(b): feature", "chore: tidy"],
        "",
        "true",
        "minor",
        "REGRESSION: a chore seen after a feat must not downgrade the bump",
    ),
    (
        ["fix(api)!: break the contract"],
        "",
        "true",
        "major",
        "a bang in the type marks a breaking change",
    ),
    (
        ["fix(api): ordinary", "feat(core)!: break it"],
        "",
        "true",
        "major",
        "REGRESSION: a breaking change in any commit wins, even below a feat",
    ),
    (
        ["fix(api): ordinary", "core: BREAKING CHANGE: gone"],
        "",
        "true",
        "major",
        "a BREAKING CHANGE footer marks a breaking change",
    ),
    (
        ["docs: prose only"],
        "feat(release): fold three repos",
        "true",
        "patch",
        "conventional commits win over the PR title when both are present",
    ),
    (
        ["Update the readme"],
        "feat(release): fold three repos",
        "true",
        "minor",
        "a non-conventional commit falls back to the PR title",
    ),
    (
        ["wip: nothing conventional"],
        "chore: still conventional",
        "true",
        "patch",
        "the PR title fallback honours chore as a patch",
    ),
    (
        ["wip: nothing conventional"],
        "",
        "true",
        "",
        "REGRESSION: nothing at all yields no bump when the requirement is enforced",
    ),
    (
        ["wip: nothing conventional"],
        "",
        "false",
        "patch",
        "REGRESSION: the same PR defaults to patch when the requirement is off",
    ),
    (
        ["chore: tidy"],
        "",
        "false",
        "patch",
        "an explicit patch survives the disabled-requirement default",
    ),
]


def main() -> int:
    script = step_script_by_id(BUMP_STEP_ID)
    # A sanity check that guards against silently testing the wrong step: if the
    # extraction ever returns something else, the assertions below could pass
    # against unrelated shell.
    if "BUMP_TYPE" not in script:
        print(f"error: extracted step {BUMP_STEP_ID!r} contains no BUMP_TYPE logic")
        return 1

    failures: list[str] = []
    for commits, title, require_conventional, expected, why in CASES:
        got, output = select_bump(commits, title, require_conventional)
        if got != expected:
            failures.append(
                f"commits={commits} title={title!r} "
                f"require_conventional={require_conventional}\n"
                f"    expected bump_type={expected!r}, got {got!r}\n"
                f"    why: {why}\n"
                f"    step output:\n{_indent(output)}"
            )

    for failure in failures:
        print(f"error: {failure}")

    print(
        f"checked {len(CASES)} bump-type selection case(s) against the "
        f"{BUMP_STEP_ID!r} step of {WF.name}"
    )
    if failures:
        return 1
    print("bump-type selection OK (single-type, mixed-type precedence, breaking changes, title fallback)")
    return 0


def _indent(text: str, prefix: str = "      ") -> str:
    return "".join(prefix + line + "\n" for line in text.strip().splitlines())


if __name__ == "__main__":
    sys.exit(main())