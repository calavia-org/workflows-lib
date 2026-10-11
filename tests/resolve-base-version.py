#!/usr/bin/env python3
"""Regression tests for the resolve-base-version composite action.

Guards the contract for resolving a base X.Y.Z version from version files or
from the highest release tag reachable from a base branch.
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
    / ".github/actions/resolve-base-version/action.yml"
)


def extract_step_script() -> str:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("id") == "resolve":
            return step["run"]
    raise KeyError("step resolve not found")


def run_action(
    *,
    source: str,
    version_file_content: str | None = None,
    tags: list[str] | None = None,
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

        if version_file_content is not None:
            (repo / "VERSION").write_text(version_file_content)

        (repo / "marker").write_text("base")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        subprocess.run(["git", "branch", "-qM", "main"], cwd=repo, check=True)

        for tag in tags or []:
            subprocess.run(["git", "tag", tag], cwd=repo, check=True)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            script_path = f.name

        output_path = repo / "out"
        env = os.environ.copy()
        env["SOURCE"] = source
        env["BASE_BRANCH"] = "main"
        env["FALLBACK"] = "0.0.0"
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
            "name": "auto reads VERSION file",
            "source": "auto",
            "version_file_content": "1.2.3\n",
            "tags": [],
            "want": {"version": "1.2.3", "source": "file"},
        },
        {
            "name": "auto falls back to highest tag",
            "source": "auto",
            "version_file_content": None,
            "tags": ["v0.1.0", "v0.10.0", "v0.2.0"],
            "want": {"version": "0.10.0", "source": "tags"},
        },
        {
            "name": "tags only ignores version file",
            "source": "tags",
            "version_file_content": "9.9.9\n",
            "tags": ["v1.0.0"],
            "want": {"version": "1.0.0", "source": "tags"},
        },
        {
            "name": "explicit version file",
            "source": "VERSION",
            "version_file_content": "2.0.0\n",
            "tags": [],
            "want": {"version": "2.0.0", "source": "file"},
        },
        {
            "name": "fallback when no file or tag",
            "source": "tags",
            "version_file_content": None,
            "tags": [],
            "want": {"version": "0.0.0", "source": "tags"},
        },
    ]

    failures = []
    for case in cases:
        got = run_action(
            source=case["source"],
            version_file_content=case.get("version_file_content"),
            tags=case.get("tags"),
        )
        want = case["want"]
        for key in want:
            if got.get(key) != want[key]:
                failures.append(
                    f"{case['name']}: {key} expected {want[key]!r}, got {got.get(key)!r}"
                )

    if failures:
        print(f"resolve-base-version FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"resolve-base-version OK ({len(cases)} cases)")
    return 0


def test_main():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
