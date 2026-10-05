#!/usr/bin/env python3
"""Regression tests for the release-github floating-tag step.

This step is the only code that moves the public `v0`-style entry point, so two
properties are pinned here that cannot be confirmed by reading the step:

1. The major is derived from the created tag, not from `new_version`. When the
   caller supplies `version` explicitly, `custom_tag` is used and `new_version`
   is not guaranteed to be emitted, so deriving from it would silently produce a
   `v` tag with an empty major.
2. An empty tag aborts *before* any push. Without the guard the step would
   compute `MAJOR_TAG="v"` and force-push a junk ref over the real entry point,
   breaking every consumer pinning the floating tag.

The step runs against a stub `git` on PATH, so the assertions cover what was
actually pushed rather than what was printed.

Exit code 0 when every case matches, 1 otherwise.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ACTION = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "actions"
    / "release-github"
    / "action.yml"
)
STEP_ID = "major-tag"

STUB_GIT = """#!/bin/sh
echo "git $*" >> "$GIT_CALLS"
exit 0
"""


def load_script() -> str:
    action = yaml.safe_load(ACTION.read_text())
    for step in action["runs"]["steps"]:
        if step.get("id") == STEP_ID:
            return step["run"]
    raise SystemExit(f"no step with id {STEP_ID!r} in {ACTION}")


def run_step(script: str, new_tag: str) -> tuple[int, str, str, str]:
    """Return (exit_code, stdout, github_output, git_calls)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        bindir = tmpdir / "bin"
        bindir.mkdir()
        stub = bindir / "git"
        stub.write_text(STUB_GIT)
        stub.chmod(0o755)

        calls = tmpdir / "calls"
        calls.write_text("")
        # The abort case writes nothing to GITHUB_OUTPUT, so it must exist before
        # the run or reading it back raises instead of yielding an empty result.
        out = tmpdir / "out"
        out.touch()

        env = {
            **os.environ,
            "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
            "NEW_TAG": new_tag,
            "GITHUB_OUTPUT": str(out),
            "GIT_CALLS": str(calls),
        }
        proc = subprocess.run(
            ["bash", "-e", "-c", script],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout, out.read_text(), calls.read_text()


# tag -> expected floating major tag
MAJOR_CASES = {
    "v1.2.3": "v1",
    "v0.15.0": "v0",
    "v10.4.2": "v10",  # two-digit major must not truncate to v1
}


def main() -> int:
    script = load_script()
    failures: list[str] = []

    for tag, expected in MAJOR_CASES.items():
        code, stdout, out, calls = run_step(script, tag)
        if code != 0:
            failures.append(f"{tag}: exit={code}, expected 0; output={stdout!r}")
        if f"major-tag={expected}" not in out:
            failures.append(f"{tag}: expected major-tag={expected}, got {out!r}")
        if f"tag -f {expected} {tag}" not in calls:
            failures.append(f"{tag}: expected 'tag -f {expected} {tag}', got {calls.strip()!r}")
        if f"push origin {expected} --force" not in calls:
            failures.append(
                f"{tag}: expected 'push origin {expected} --force', got {calls.strip()!r}"
            )

    code, stdout, out, calls = run_step(script, "")
    if code == 0:
        failures.append("empty tag: expected non-zero exit, got 0")
    if "::error::" not in stdout:
        failures.append(f"empty tag: expected ::error:: annotation, got {stdout!r}")
    if "push" in calls:
        failures.append(f"empty tag: expected no push, got {calls.strip()!r}")
    if "major-tag=" in out:
        failures.append(f"empty tag: expected no major-tag output, got {out!r}")

    if failures:
        print(f"floating-tag FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    total = len(MAJOR_CASES) + 1
    print(
        f"floating-tag OK ({total} cases: "
        f"{len(MAJOR_CASES)} majors, 1 empty-tag abort)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
