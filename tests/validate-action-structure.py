#!/usr/bin/env python3
"""Regression tests for the validate-action-structure composite action.

Checks that composite action metadata meets the structural contract required
by the reusable-workflow consumers: name, description, runs.using.
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
    / ".github/actions/validate-action-structure/action.yml"
)


def extract_step_script() -> str:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("id") == "validate":
            return step["run"]
    raise KeyError("step validate not found")


def run_action(*, action_yaml: str, require_composite: str = "true") -> tuple[int, dict[str, str]]:
    script = extract_step_script()

    with tempfile.TemporaryDirectory() as tmp:
        action_file = Path(tmp) / "action.yml"
        action_file.write_text(action_yaml)
        output_path = Path(tmp) / "out"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            script_path = f.name

        env = os.environ.copy()
        env["ACTION_FILE"] = str(action_file)
        env["REQUIRE_COMPOSITE"] = require_composite
        env["GITHUB_OUTPUT"] = str(output_path)

        try:
            result = subprocess.run(
                ["bash", script_path],
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

    return result.returncode, outputs


def main() -> int:
    valid_composite = """name: Valid Action
description: A valid composite action
runs:
  using: composite
  steps:
    - run: echo ok
      shell: bash
"""

    missing_name = """description: missing name
runs:
  using: composite
  steps: []
"""

    missing_description = """name: Missing Description
runs:
  using: composite
  steps: []
"""

    non_composite = """name: Non Composite
description: uses node16
runs:
  using: node16
  main: index.js
"""

    invalid_yaml = """name: Broken
description: not valid yaml
  bad indent
"""

    cases = [
        {
            "name": "valid composite",
            "yaml": valid_composite,
            "require_composite": "true",
            "want_rc": 0,
            "want": {"valid": "true", "name": "Valid Action", "using": "composite"},
        },
        {
            "name": "missing name fails",
            "yaml": missing_name,
            "require_composite": "true",
            "want_rc": 1,
            "want": {},
        },
        {
            "name": "missing description fails",
            "yaml": missing_description,
            "require_composite": "true",
            "want_rc": 1,
            "want": {},
        },
        {
            "name": "non composite fails when required",
            "yaml": non_composite,
            "require_composite": "true",
            "want_rc": 1,
            "want": {},
        },
        {
            "name": "non composite allowed",
            "yaml": non_composite,
            "require_composite": "false",
            "want_rc": 0,
            "want": {"valid": "true", "name": "Non Composite", "using": "node16"},
        },
        {
            "name": "invalid yaml fails",
            "yaml": invalid_yaml,
            "require_composite": "true",
            "want_rc": 1,
            "want": {},
        },
    ]

    failures = []
    for case in cases:
        rc, got = run_action(
            action_yaml=case["yaml"],
            require_composite=case["require_composite"],
        )
        if rc != case["want_rc"]:
            failures.append(f"{case['name']}: expected exit {case['want_rc']}, got {rc}")
        for key, value in case["want"].items():
            if got.get(key) != value:
                failures.append(
                    f"{case['name']}: {key} expected {value!r}, got {got.get(key)!r}"
                )

    if failures:
        print(f"validate-action-structure FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"validate-action-structure OK ({len(cases)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
