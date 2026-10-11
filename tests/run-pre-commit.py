#!/usr/bin/env python3
"""Invariant tests for the run-pre-commit composite action.

Guards that the action uses mise to manage Python, avoids the forbidden 3.9
runtime, and invokes pre-commit with the expected flags. A full behavioral test
(running pre-commit inside the action) is left to the CI job that consumes this
action; this suite checks the contract without needing network or mise installed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / ".github/actions/run-pre-commit/action.yml"
MISE = REPO / "mise.toml"


def action_steps() -> list[dict]:
    data = yaml.safe_load(ACTION.read_text())
    return data["runs"]["steps"]


def _mise_python_version() -> str:
    # mise.toml is TOML, not YAML; parse the small pinned-tools section directly
    # to keep the test's only dependency as pyyaml.
    assert MISE.exists(), "mise.toml is missing"

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

    assert version, "mise.toml does not pin a Python version"
    major, minor, *_ = str(version).split(".")
    assert int(major) > 3 or (int(major) == 3 and int(minor) >= 10), (
        f"Python {version} is too old; must be >= 3.10"
    )
    return version


def test_mise_python_version():
    version = _mise_python_version()
    print(f"run-pre-commit OK: mise.toml pins Python {version}")


def test_action_uses_mise():
    steps = action_steps()
    uses = [step.get("uses", "") for step in steps]
    assert any("mise-action" in u for u in uses), (
        "action does not use jdx/mise-action"
    )
    print("run-pre-commit OK: action uses mise tooling")


def test_action_runs_precommit_all_files():
    steps = action_steps()
    runs = [step.get("run", "") for step in steps]
    assert any("pre-commit run" in r and "--all-files" in r for r in runs), (
        "action does not run 'pre-commit run --all-files'"
    )
    print("run-pre-commit OK: action runs pre-commit on all files")


def test_all():
    test_mise_python_version()
    test_action_uses_mise()
    test_action_runs_precommit_all_files()
    print("\nrun-pre-commit OK")


if __name__ == "__main__":
    test_all()
