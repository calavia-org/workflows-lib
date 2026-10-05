#!/usr/bin/env python3
"""Verify the bump guard detects an applied bump from PR state, not commit text.

The guard used to read `git log -1` and grep for "chore: bump version". That is a
question about the last commit, and a human push on top of the bot's bump commit
changed the answer: the guard reopened, `base-version-source: file` handed the
already-bumped PR-head version straight to the bump action, and the PR advanced
0.16.0 -> 0.17.0. Review feedback is the normal case, not an edge case.

The invariant these cases pin down: a bump has been applied exactly when the
version committed at the PR head differs from the version the base branch has
released. That is independent of which commit landed last.
"""

import pathlib
import subprocess
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WF = ROOT / ".github/workflows/pr-check-and-bump.yml"
GUARD_STEP_ID = "last_commit"

# The guard this file is written against, quoted so the suite documents the bug
# rather than only the current behaviour.
LEGACY_GUARD = """
LAST_COMMIT=$(git log -1 --pretty=%B)
if echo "$LAST_COMMIT" | grep -q "chore: bump version"; then
  echo "already_bumped=true" >> "$GITHUB_OUTPUT"
else
  echo "already_bumped=false" >> "$GITHUB_OUTPUT"
fi
"""


def guard_script():
    """Return the guard step's run script, verbatim."""
    doc = yaml.safe_load(WF.read_text())
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if step.get("id") == GUARD_STEP_ID:
                return step["run"]
    raise SystemExit(f"guard step id not found: {GUARD_STEP_ID}")


def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


def build_repo(tmp, base_tag, head_commits):
    """Create main (carrying `base_tag`) plus a feat branch with head_commits.

    Each head commit is a (message, version_or_None) pair; version_or_None leaves
    the version file untouched, which is what a review-fix push does.
    """
    repo = str(pathlib.Path(tmp) / "repo")
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    pathlib.Path(repo, "VERSION").write_text("0.0.0\n")
    _git(repo, "add", "VERSION")
    _git(repo, "commit", "-q", "-m", "base")
    if base_tag is not None:
        _git(repo, "tag", base_tag)
    # The base branch is fetched as its own remote, exactly as CI does, so
    # `origin/main` and `--merged` resolve during the guard.
    bare = str(pathlib.Path(tmp) / "origin.git")
    subprocess.run(["git", "clone", "-q", "--bare", repo, bare], check=True)
    _git(repo, "remote", "add", "origin", bare)
    _git(repo, "fetch", "-q", "origin", "main", "--tags")
    _git(repo, "checkout", "-q", "-b", "feat/consolidate-actions")
    for message, version in head_commits:
        if version is not None:
            pathlib.Path(repo, "VERSION").write_text(f"{version}\n")
            _git(repo, "add", "VERSION")
        _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return repo


def run_guard(script, repo, version_file="VERSION"):
    """Run the guard and return (already_bumped, log)."""
    with tempfile.TemporaryDirectory() as out:
        env_out = str(pathlib.Path(out) / "out")
        full = (
            f"export GITHUB_OUTPUT={env_out}\n"
            f"export BASE_BRANCH=main\n"
            f"export VERSION_FILE={version_file}\n"
            f"cd {repo}\n"
            + script
        )
        proc = subprocess.run(["bash", "-c", full], capture_output=True, text=True)
        try:
            body = pathlib.Path(env_out).read_text()
        except FileNotFoundError:
            body = ""
        return "already_bumped=true" in body, proc.stdout + proc.stderr


CASES = [
    (
        "fresh PR: head version equals the released base tag -> bump proceeds",
        "v0.16.0",
        [("feat: consolidate actions", "0.16.0")],
        False,
        False,
    ),
    (
        "bot bump already applied at the head -> bump skipped",
        "v0.15.0",
        [
            ("feat: consolidate actions", "0.16.0"),
            ("chore: bump version to 0.16.0 (minor)", None),
        ],
        True,
        True,
    ),
    (
        "REGRESSION: human review fix on top of the bump -> still skipped",
        "v0.15.0",
        [
            ("feat: consolidate actions", "0.16.0"),
            ("chore: bump version to 0.16.0 (minor)", None),
            ("fix(docs): address review feedback", None),
        ],
        True,
        True,
    ),
    (
        "review fix as the very first push on a bumped head -> still skipped",
        "v0.15.0",
        [
            ("feat: consolidate actions", "0.16.0"),
            ("chore: bump version to 0.16.0 (minor)", None),
            ("refactor: unrelated", None),
            ("fix: second review round", None),
        ],
        True,
        True,
    ),
]


def main():
    script = guard_script()
    failures = []
    for name, base_tag, commits, expect, legacy_expect in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            repo = build_repo(tmp, base_tag, commits)
            got, log = run_guard(script, repo)
            legacy, _ = run_guard(LEGACY_GUARD, repo)

        status = "ok" if got == expect else "FAILED"
        if got != expect:
            failures.append((name, expect, got, log))

        marker = ""
        if expect and not legacy_expect:
            marker = "  <- legacy guard gets this wrong"
        elif legacy != legacy_expect:
            marker = f"  (legacy guard: {legacy})"
        print(f"  {status:6} already_bumped={got} (want {expect}){marker}")
        print(f"         {name}")

    if failures:
        print(f"\n{len(failures)} case(s) failed:")
        for name, expect, got, log in failures:
            print(f"\n  {name}\n    expected already_bumped={expect}, got {got}")
            print("    " + log.replace("\n", "\n    "))
        return 1

    print(f"\nall {len(CASES)} cases passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())