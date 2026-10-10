#!/usr/bin/env python3
"""Regression tests for the validate-branch composite action.

Replays the action's bash steps against synthetic inputs and asserts the
contractal outputs: branch-valid, target-valid, and should-bump.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ACTION = (
    Path(__file__).resolve().parent.parent / ".github/actions/validate-branch/action.yml"
)

CASES = [
    {
        "name": "feature branch to main",
        "inputs": {
            "branch": "feat/new-thing",
            "allowed-branch-pattern": r"^(major|feat|fix|doc)/.+",
            "target-branch": "main",
            "allowed-target-branches": "main,release/*",
            "no-bump-branch-pattern": r"^doc/.+",
        },
        "want": {"branch-valid": "true", "target-valid": "true", "should-bump": "true"},
    },
    {
        "name": "docs branch skips bump",
        "inputs": {
            "branch": "doc/readme-update",
            "allowed-branch-pattern": r"^(major|feat|fix|doc)/.+",
            "target-branch": "main",
            "allowed-target-branches": "main,release/*",
            "no-bump-branch-pattern": r"^doc/.+",
        },
        "want": {"branch-valid": "true", "target-valid": "true", "should-bump": "false"},
    },
    {
        "name": "invalid branch name",
        "inputs": {
            "branch": "random-branch",
            "allowed-branch-pattern": r"^(major|feat|fix|doc)/.+",
            "target-branch": "main",
            "allowed-target-branches": "main,release/*",
            "no-bump-branch-pattern": "",
        },
        "want": {"branch-valid": "false", "target-valid": "true", "should-bump": "true"},
    },
    {
        "name": "target release branch",
        "inputs": {
            "branch": "fix/critical",
            "allowed-branch-pattern": r"^(major|feat|fix|doc)/.+",
            "target-branch": "release/1.2",
            "allowed-target-branches": "main,release/*",
            "no-bump-branch-pattern": "",
        },
        "want": {"branch-valid": "true", "target-valid": "true", "should-bump": "true"},
    },
    {
        "name": "disallowed target branch",
        "inputs": {
            "branch": "fix/critical",
            "allowed-branch-pattern": r"^(major|feat|fix|doc)/.+",
            "target-branch": "develop",
            "allowed-target-branches": "main,release/*",
            "no-bump-branch-pattern": "",
        },
        "want": {"branch-valid": "true", "target-valid": "false", "should-bump": "true"},
    },
    {
        "name": "validation disabled",
        "inputs": {
            "branch": "anything-goes",
            "allowed-branch-pattern": "",
            "target-branch": "main",
            "allowed-target-branches": "main,release/*",
            "no-bump-branch-pattern": "",
        },
        "want": {"branch-valid": "true", "target-valid": "true", "should-bump": "true"},
    },
]


def extract_step_script(action: Path, step_id: str) -> str:
    data = yaml.safe_load(action.read_text())
    for step in data["runs"]["steps"]:
        if step.get("id") == step_id:
            return step["run"]
    raise KeyError(f"step {step_id} not found in {action}")


def run_step(step_id: str, inputs: dict[str, str]) -> dict[str, str]:
    script = extract_step_script(ACTION, step_id)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        f.write(script)
        f.flush()
        script_path = f.name

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".out", delete=False) as out:
        output_path = out.name

    env = os.environ.copy()
    env.update(inputs)
    env["GITHUB_OUTPUT"] = output_path

    try:
        result = subprocess.run(
            ["bash", script_path],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        with open(output_path) as f:
            outputs = {}
            for line in f.read().splitlines():
                if "=" in line:
                    key, _, value = line.partition("=")
                    outputs[key.strip()] = value.strip()
        if result.returncode != 0:
            outputs["_error"] = result.stderr.strip()
    finally:
        os.unlink(script_path)
        os.unlink(output_path)

    return outputs


def main() -> int:
    failures = []
    for case in CASES:
        name = case["name"]
        inputs = case["inputs"]
        want = case["want"]

        env = {
            "BRANCH": inputs["branch"],
            "PATTERN": inputs["allowed-branch-pattern"],
            "TARGET": inputs["target-branch"],
            "ALLOWED": inputs["allowed-target-branches"],
        }

        no_bump_env = {
            "BRANCH": inputs["branch"],
            "PATTERN": inputs["no-bump-branch-pattern"],
        }

        got_no_bump = run_step("check-no-bump", no_bump_env)

        if inputs["allowed-branch-pattern"]:
            got_branch = run_step("validate-branch", env)
        else:
            got_branch = run_step("validate-branch-disabled", {})

        got_target = run_step("validate-target", env)

        got = {
            "branch-valid": got_branch.get("valid", ""),
            "target-valid": got_target.get("valid", ""),
            "should-bump": got_no_bump.get("should_bump", ""),
        }

        for key in want:
            if got.get(key) != want[key]:
                failures.append(f"{name}: {key} expected {want[key]!r}, got {got[key]!r}")

    if failures:
        print(f"validate-branch FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"validate-branch OK ({len(CASES)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
