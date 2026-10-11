#!/usr/bin/env python3
"""Regression tests for the verify-required-tests-passed composite action.

Ensures the merge gate accepts success, accepts skipped for optional jobs, and
rejects failure or cancellation for any required job.
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
    / ".github/actions/verify-required-tests-passed/action.yml"
)


def extract_step_script() -> str:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("id") == "verify":
            return step["run"]
    raise KeyError("step verify not found")


def run_action(*, unit="success", integration="skipped", build="success", package="success", pre_commit="success") -> tuple[int, dict[str, str]]:
    script = extract_step_script()

    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "out"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            script_path = f.name

        env = os.environ.copy()
        env["UNIT_RESULT"] = unit
        env["INTEGRATION_RESULT"] = integration
        env["BUILD_RESULT"] = build
        env["PACKAGE_RESULT"] = package
        env["PRE_COMMIT_RESULT"] = pre_commit
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
    cases = [
        {
            "name": "all success",
            "results": {},
            "want_rc": 0,
            "want_passed": "true",
        },
        {
            "name": "unit failure fails",
            "results": {"unit": "failure"},
            "want_rc": 1,
            "want_passed": "",
        },
        {
            "name": "integration cancelled fails",
            "results": {"integration": "cancelled"},
            "want_rc": 1,
            "want_passed": "",
        },
        {
            "name": "build skipped allowed",
            "results": {"build": "skipped"},
            "want_rc": 0,
            "want_passed": "true",
        },
        {
            "name": "pre-commit failure fails",
            "results": {"pre_commit": "failure"},
            "want_rc": 1,
            "want_passed": "",
        },
        {
            "name": "package failure fails",
            "results": {"package": "failure"},
            "want_rc": 1,
            "want_passed": "",
        },
    ]

    failures = []
    defaults = {
        "unit": "success",
        "integration": "skipped",
        "build": "success",
        "package": "success",
        "pre_commit": "success",
    }

    for case in cases:
        params = defaults.copy()
        params.update(case["results"])
        rc, outputs = run_action(**params)
        if rc != case["want_rc"]:
            failures.append(f"{case['name']}: expected exit {case['want_rc']}, got {rc}")
        got_passed = outputs.get("passed", "")
        if got_passed != case["want_passed"]:
            failures.append(
                f"{case['name']}: expected passed={case['want_passed']!r}, got {got_passed!r}"
            )

    if failures:
        print(f"verify-required-tests-passed FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"verify-required-tests-passed OK ({len(cases)} cases)")
    return 0


def test_main():
    assert main() == 0

if __name__ == "__main__":
    sys.exit(main())
