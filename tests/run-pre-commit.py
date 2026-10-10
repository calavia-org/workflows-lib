#!/usr/bin/env python3
"""Invariant tests for the run-pre-commit composite action.

Guards that the action uses mise to manage Python, avoids the forbidden 3.9
runtime, and invokes pre-commit with the expected flags. A full behavioral test
(running pre-commit inside the action) is left to the CI job that consumes this
action; this suite checks the contract without needing network or mise installed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / ".github/actions/run-pre-commit/action.yml"
MISE = REPO / "mise.toml"


def action_steps() -> list[dict]:
    data = yaml.safe_load(ACTION.read_text())
    return data["runs"]["steps"]


def test_mise_python_version() -> int:
    if not MISE.exists():
        print("run-pre-commit FAILED: mise.toml is missing")
        return 1

    # mise.toml is TOML, not YAML; parse the small pinned-tools section directly
    # to keep the test's only dependency as pyyaml.
    version = ""
    in_tools = False
    for line in MISE.read_text().splitlines():
        stripped = line.strip()
        if stripped == "[tools]":
            in_tools = True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_tools = False
            continue
        if in_tools and stripped.startswith("python"):
            _, _, value = stripped.partition("=")
            version = value.strip().strip('"').strip("'")
            break
    if not version:
        print("run-pre-commit FAILED: mise.toml does not pin a Python version")
        return 1

    major, minor, *_ = str(version).split(".")
    if int(major) < 3 or (int(major) == 3 and int(minor) < 10):
        print(f"run-pre-commit FAILED: Python {version} is too old; must be >= 3.10")
        return 1

    print(f"run-pre-commit OK: mise.toml pins Python {version}")
    return 0


def test_action_uses_mise() -> int:
    steps = action_steps()
    for step in steps:
        uses = step.get("uses", "")
        if "mise-action" in uses:
            print(f"run-pre-commit OK: action uses mise tooling ({uses})")
            return 0

    print("run-pre-commit FAILED: action does not use jdx/mise-action")
    return 1


def test_action_runs_precommit_all_files() -> int:
    steps = action_steps()
    for step in steps:
        run = step.get("run", "")
        if "pre-commit run" in run and "--all-files" in run:
            print("run-pre-commit OK: action runs pre-commit on all files")
            return 0

    print("run-pre-commit FAILED: action does not run 'pre-commit run --all-files'")
    return 1


def main() -> int:
    failures = 0
    for check in (test_mise_python_version, test_action_uses_mise, test_action_runs_precommit_all_files):
        if check() != 0:
            failures += 1

    if failures:
        print(f"\nrun-pre-commit FAILED: {failures} check(s)")
        return 1

    print("\nrun-pre-commit OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
