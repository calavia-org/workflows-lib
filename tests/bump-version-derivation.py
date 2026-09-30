#!/usr/bin/env python3
"""Verify how pr-check-and-bump.yml derives the base version for a bump.

The derivation logic is EXTRACTED FROM THE WORKFLOW and executed with bash
against synthetic tag sets, so this tests the shipped shell rather than a
transcription of it.

Regression guarded: `git describe --tags` returns the most RECENT tag by
commit distance, so a prerelease tag (v0.0.0-pr.54) wins over a much higher
release tag (v1.7.1). That made bump-version-action compute 0.0.1 and
silently roll a released collection back, e.g. on every push to a dependabot
branch whose auto-bump re-derived the base version.
"""
import re
import subprocess
import sys
import tempfile

import yaml

WF = ".github/workflows/pr-check-and-bump.yml"
DERIVE_STEP_ID = "current"
COMMIT_STEP = "Commit and push version bump"


def _steps():
    with open(WF) as fh:
        doc = yaml.safe_load(fh)
    for job in (doc.get("jobs") or {}).values():
        yield from (job.get("steps") or [])


def step_script_by_id(step_id):
    for step in _steps():
        if step.get("id") == step_id:
            return step["run"]
    raise SystemExit(f"step id not found: {step_id}")


def step_script(name):
    """Return the run: script of the named step, verbatim."""
    for step in _steps():
        if step.get("name") == name:
            return step["run"]
    raise SystemExit(f"step not found: {name}")


def derive(tags, base="main"):
    """Run the workflow's derivation against a synthetic repo of `tags`."""
    script = step_script_by_id(DERIVE_STEP_ID)
    with tempfile.TemporaryDirectory() as tmp:
        repo = f"{tmp}/repo"
        # A real (non-bare) repo with one commit, so `--merged` and tag listing
        # behave exactly as they do in CI.
        subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
        for cmd in (
            ["git", "-C", repo, "config", "user.email", "t@example.com"],
            ["git", "-C", repo, "config", "user.name", "T"],
            ["git", "-C", repo, "commit", "-q", "--allow-empty", "-m", "base"],
            ["git", "-C", repo, "remote", "add", "origin", repo],
        ):
            subprocess.run(cmd, check=True)
        for tag in tags:
            subprocess.run(["git", "-C", repo, "tag", tag], check=True)
        subprocess.run(
            ["git", "-C", repo, "fetch", "-q", "origin", base, "--tags"],
            capture_output=True,
        )
        env_out = f"{tmp}/out"
        full = (
            f"export GITHUB_OUTPUT={env_out}\n"
            f"export GITHUB_ENV={env_out}.env\n"
            f"export BASE_BRANCH={base}\n"
            f"cd {repo}\n"
            + script
        )
        proc = subprocess.run(
            ["bash", "-c", full], capture_output=True, text=True
        )
        got = None
        try:
            with open(env_out) as fh:
                for line in fh:
                    if line.startswith("version="):
                        got = line.split("=", 1)[1].strip()
        except FileNotFoundError:
            pass
        return got, proc.stdout + proc.stderr


def forward_guard(base_version, new_version):
    """Run the workflow's refuse-to-downgrade guard; return True if it aborts."""
    script = step_script(COMMIT_STEP)
    # Keep only the guard, drop the git push that follows it.
    script = script.split("git add")[0]
    # The step interpolates GitHub expressions into shell assignments; neutralise
    # them so bash can run the script outside Actions.
    script = re.sub(r"\$\{\{[^}]*\}\}", "", script)
    full = (
        "set -e\n"
        "FILE=v.txt; TYPE=patch\n"
        f"export BASE_VERSION={base_version}\n"
        f"export NEW_VERSION={new_version}\n"
        + script
    )
    proc = subprocess.run(["bash", "-c", full], capture_output=True, text=True)
    return proc.returncode != 0, proc.stdout + proc.stderr


CASES = [
    # (tags, expected, why) — BASE_BRANCH is bare, as github.base_ref supplies it
    (["v1.7.0", "v1.7.1"], "1.7.1", "highest release tag wins"),
    (["v1.6.0", "v1.7.1", "v0.0.0-pr.54", "v0.0.0-pr.60"], "1.7.1",
     "REGRESSION: prerelease tags must not win over release tags"),
    (["v0.0.0-pr.54"], "0.0.0", "only prerelease tags → 0.0.0 fallback"),
    ([], "0.0.0", "no tags at all → 0.0.0 fallback"),
    (["v2.0.0-rc.1", "v1.9.0"], "1.9.0", "non -pr. suffixes ignored too"),
    (["v1.7.1", "v1.7.10"], "1.7.10", "numeric sort, not lexicographic"),
]

GUARDS = [
    ("1.7.1", "1.7.2", False, "patch bump is a forward move"),
    ("1.7.1", "1.8.0", False, "minor bump is a forward move"),
    ("1.7.1", "1.7.1", True, "no-op bump must be refused"),
    ("0.0.0-pr.54", "0.0.1", True, "REGRESSION: 0.0.1 from a prerelease base must be refused"),
    ("1.7.1", "0.0.1", True, "REGRESSION: downgrade must be refused"),
]


def main():
    failures = []

    print("base version derivation")
    for tags, expected, why in CASES:
        got, log = derive(tags)
        ok = got == expected
        print(f"  {'PASS' if ok else 'FAIL'}  expect={expected:<8} got={str(got):<8} {why}")
        if not ok:
            failures.append(f"derivation {tags}: expected {expected}, got {got}")
            print(log)

    print("\nforward-move guard")
    for base_v, new_v, should_refuse, why in GUARDS:
        refused, log = forward_guard(base_v, new_v)
        ok = refused == should_refuse
        print(f"  {'PASS' if ok else 'FAIL'}  {base_v} → {new_v}  refuse={refused} (want {should_refuse})  {why}")
        if not ok:
            failures.append(f"guard {base_v}->{new_v}: expected refuse={should_refuse}, got {refused}")
            print(log)

    if failures:
        print(f"\n{len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"\nall {len(CASES) + len(GUARDS)} cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())