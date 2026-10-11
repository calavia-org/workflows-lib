#!/usr/bin/env python3
"""Regression tests for the check-already-bumped composite action.

Detects whether a PR branch already carries a version bump by comparing the
committed version file at HEAD against the latest release tag on the base
branch.
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
    / ".github/actions/check-already-bumped/action.yml"
)


def extract_step_script() -> str:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("id") == "check":
            return step["run"]
    raise KeyError("step check not found")


def run_action(
    *,
    head_version: str,
    base_version: str,
    base_tags: list[str] | None = None,
) -> dict[str, str]:
    script = extract_step_script()

    with tempfile.TemporaryDirectory() as repo_dir:
        repo = Path(repo_dir)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo, check=True
        )

        (repo / "VERSION").write_text(base_version + "\n")
        (repo / "marker").write_text("base")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        subprocess.run(["git", "branch", "-qM", "main"], cwd=repo, check=True)

        for tag in base_tags or []:
            subprocess.run(["git", "tag", tag], cwd=repo, check=True)

        subprocess.run(["git", "checkout", "-qb", "pr-branch"], cwd=repo, check=True)
        (repo / "marker").write_text("pr-change")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "pr change"], cwd=repo, check=True)
        (repo / "VERSION").write_text(head_version + "\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "update version"], cwd=repo, check=True)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            script_path = f.name

        output_path = repo / "out"
        env = os.environ.copy()
        env["BASE_BRANCH"] = "main"
        env["VERSION_FILE_INPUT"] = "auto"
        env["GITHUB_OUTPUT"] = str(output_path)

        try:
            subprocess.run(
                ["bash", script_path],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            outputs = {}
            if output_path.exists():
                for line in output_path.read_text().splitlines():
                    if "=" in line:
                        key, _, value = line.partition("=")
                        outputs[key.strip()] = value.strip()
        finally:
            os.unlink(script_path)

    return outputs


def main() -> int:
    cases = [
        {
            "name": "head newer than base tag",
            "head_version": "1.1.0",
            "base_version": "0.9.9",
            "base_tags": ["v1.0.0"],
            "want": {"already_bumped": "true"},
        },
        {
            "name": "head equals base tag",
            "head_version": "1.0.0",
            "base_version": "0.9.9",
            "base_tags": ["v1.0.0"],
            "want": {"already_bumped": "false"},
        },
        {
            "name": "no base tag",
            "head_version": "1.0.0",
            "base_version": "0.9.9",
            "base_tags": [],
            "want": {"already_bumped": "false"},
        },
    ]

    failures = []
    for case in cases:
        got = run_action(
            head_version=case["head_version"],
            base_version=case["base_version"],
            base_tags=case.get("base_tags"),
        )
        want = case["want"]
        for key in want:
            if got.get(key) != want[key]:
                failures.append(
                    f"{case['name']}: {key} expected {want[key]!r}, got {got.get(key)!r}"
                )

    if failures:
        print(f"check-already-bumped FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"check-already-bumped OK ({len(cases)} cases)")
    return 0


def test_main():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
