#!/usr/bin/env python3
"""Regression tests for the select-pre-release-artifacts composite action.

Guards the pre-release artifact selector contract: only 'binary' is accepted,
auto/empty/missing-dir are failures, and resolved paths are returned.
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
    / ".github/actions/select-pre-release-artifacts/action.yml"
)


def extract_step_script() -> str:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("id") == "select":
            return step["run"]
    raise KeyError("step select not found")


def run_action(*, selector: str, create_empty: bool = False) -> tuple[int, dict[str, str]]:
    script = extract_step_script()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        artifacts_path = tmp_path / "pre-release-artifacts"
        if create_empty:
            artifacts_path.mkdir()
        elif selector == "binary":
            artifacts_path.mkdir()
            (artifacts_path / "app.tar.gz").write_text("binary")
            (artifacts_path / "checksums.txt").write_text("checksums")

        output_path = tmp_path / "out"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            script_path = f.name

        env = os.environ.copy()
        env["SELECTED"] = selector
        env["ARTIFACTS_DIR"] = str(artifacts_path)
        env["GITHUB_OUTPUT"] = str(output_path)

        try:
            result = subprocess.run(
                ["bash", script_path],
                cwd=tmp_path,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            outputs = {}
            if output_path.exists():
                text = output_path.read_text()
                if "paths<<EOF" in text:
                    lines = text.splitlines()
                    in_paths = False
                    paths = []
                    for line in lines:
                        if line == "paths<<EOF":
                            in_paths = True
                            continue
                        if line == "EOF":
                            break
                        if in_paths:
                            paths.append(line)
                    outputs["paths"] = "\n".join(paths)
        finally:
            os.unlink(script_path)

    return result.returncode, outputs


def main() -> int:
    cases = [
        {
            "name": "binary with artifacts",
            "selector": "binary",
            "create_empty": False,
            "want_rc": 0,
            "want_paths": 2,
        },
        {
            "name": "empty selector fails",
            "selector": "",
            "create_empty": False,
            "want_rc": 1,
            "want_paths": 0,
        },
        {
            "name": "auto selector fails",
            "selector": "auto",
            "create_empty": False,
            "want_rc": 1,
            "want_paths": 0,
        },
        {
            "name": "docker selector fails",
            "selector": "docker",
            "create_empty": False,
            "want_rc": 1,
            "want_paths": 0,
        },
        {
            "name": "binary with empty dir fails",
            "selector": "binary",
            "create_empty": True,
            "want_rc": 1,
            "want_paths": 0,
        },
    ]

    failures = []
    for case in cases:
        rc, outputs = run_action(
            selector=case["selector"],
            create_empty=case["create_empty"],
        )
        if rc != case["want_rc"]:
            failures.append(f"{case['name']}: expected exit {case['want_rc']}, got {rc}")
            continue
        path_count = len(outputs.get("paths", "").splitlines()) if outputs.get("paths") else 0
        if path_count != case["want_paths"]:
            failures.append(
                f"{case['name']}: expected {case['want_paths']} paths, got {path_count}"
            )

    if failures:
        print(f"select-pre-release-artifacts FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"select-pre-release-artifacts OK ({len(cases)} cases)")
    return 0


def test_main():
    assert main() == 0

if __name__ == "__main__":
    sys.exit(main())
