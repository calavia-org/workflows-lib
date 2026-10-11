#!/usr/bin/env python3
"""Regression tests for the parse-conventional-commits composite action.

Replays the action's bash against synthetic git histories and PR titles and
pins the bump-type priority: major > minor > patch.
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
    / ".github/actions/parse-conventional-commits/action.yml"
)


def extract_step_script() -> str:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("id") == "parse":
            return step["run"]
    raise KeyError("step parse not found")


def run_action(
    *,
    commits: list[str],
    pr_title: str = "",
    require: bool = False,
    default: str = "patch",
) -> dict[str, str]:
    script = extract_step_script()

    with tempfile.TemporaryDirectory() as repo_dir:
        repo = Path(repo_dir)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo,
            check=True,
        )
        (repo / "file").write_text("base")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "chore: base"], cwd=repo, check=True)
        subprocess.run(["git", "branch", "-qM", "main"], cwd=repo, check=True)
        subprocess.run(
            ["git", "checkout", "-qb", "pr-branch"],
            cwd=repo,
            check=True,
        )

        for msg in commits:
            (repo / "file").write_text(msg)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", msg], cwd=repo, check=True)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            script_path = f.name

        output_path = repo / "github_output"

        env = os.environ.copy()
        env["BASE_BRANCH"] = "main"
        env["PR_TITLE"] = pr_title
        env["REQUIRE_CONVENTIONAL"] = "true" if require else "false"
        env["DEFAULT_BUMP"] = default
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
            "name": "fix only",
            "commits": ["fix: handle null"],
            "want": {"bump_type": "patch", "has_conventional": "true"},
        },
        {
            "name": "feat only",
            "commits": ["feat: add auth"],
            "want": {"bump_type": "minor", "has_conventional": "true"},
        },
        {
            "name": "breaking only",
            "commits": ["feat!: remove v1"],
            "want": {
                "bump_type": "major",
                "has_conventional": "true",
                "breaking": "true",
            },
        },
        {
            "name": "fix and feat yields minor",
            "commits": ["fix: bug", "feat: feature"],
            "want": {"bump_type": "minor", "has_conventional": "true"},
        },
        {
            "name": "feat and breaking yields major",
            "commits": ["feat: feature", "refactor!: drop old api"],
            "want": {
                "bump_type": "major",
                "has_conventional": "true",
                "breaking": "true",
            },
        },
        {
            "name": "non-conventional defaults to patch",
            "commits": ["random commit"],
            "want": {"bump_type": "patch", "has_conventional": "false"},
        },
        {
            "name": "pr title fallback",
            "commits": ["random commit"],
            "pr_title": "feat: add widget",
            "want": {"bump_type": "minor", "has_conventional": "true"},
        },
        {
            "name": "pr title breaking fallback",
            "commits": [],
            "pr_title": "fix!: breaking fix",
            "want": {
                "bump_type": "major",
                "has_conventional": "true",
                "breaking": "true",
            },
        },
    ]

    failures = []
    for case in cases:
        got = run_action(
            commits=case["commits"],
            pr_title=case.get("pr_title", ""),
        )
        want = case["want"]
        for key in want:
            if got.get(key) != want[key]:
                failures.append(
                    f"{case['name']}: {key} expected {want[key]!r}, got {got.get(key)!r}"
                )

    if failures:
        print(f"parse-conventional-commits FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"parse-conventional-commits OK ({len(cases)} cases)")
    return 0


def test_main():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
