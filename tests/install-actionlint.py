#!/usr/bin/env python3
"""Regression tests for the install-actionlint composite action.

Verifies that the requested actionlint version is downloaded and executable on
the current platform.
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
    / ".github/actions/install-actionlint/action.yml"
)


def extract_step_script() -> str:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("id") == "install":
            return step["run"]
    raise KeyError("step install not found")


def run_action(*, version: str) -> tuple[int, str, str]:
    script = extract_step_script()

    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "out"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            script_path = f.name

        env = os.environ.copy()
        env["VERSION"] = version
        env["RUNNER_OS"] = "macOS"
        env["RUNNER_ARCH"] = "ARM64"
        env["RUNNER_TOOL_CACHE"] = str(tmp)
        env["GITHUB_OUTPUT"] = str(output_path)

        try:
            result = subprocess.run(
                ["bash", script_path],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            actionlint_path = ""
            if output_path.exists():
                for line in output_path.read_text().splitlines():
                    if line.startswith("actionlint_path="):
                        actionlint_path = line.partition("=")[2].strip()

            installed_version = ""
            if actionlint_path and Path(actionlint_path).exists():
                ver_result = subprocess.run(
                    [actionlint_path, "--version"],
                    capture_output=True,
                    text=True,
                )
                installed_version = (
                    ver_result.stdout.strip().split()[0] if ver_result.stdout else ""
                )
        finally:
            os.unlink(script_path)

    return result.returncode, actionlint_path, installed_version


def main() -> int:
    version = "1.7.3"
    rc, path, installed_version = run_action(version=version)

    if rc != 0:
        print(f"install-actionlint FAILED: action returned exit code {rc}")
        return 1

    if not path:
        print("install-actionlint FAILED: actionlint_path output is empty")
        return 1

    if installed_version != version:
        print(
            f"install-actionlint FAILED: expected version {version}, got {installed_version}"
        )
        return 1

    print(f"install-actionlint OK (version {installed_version} at {path})")
    return 0


def test_main():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
