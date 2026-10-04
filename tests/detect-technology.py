#!/usr/bin/env python3
"""Regression tests for technology detection.

These run the composite action's own bash script against synthetic repositories,
so the assertions describe what consumers actually observe rather than what the
script appears to intend.

The `primary` vocabulary is contractual: `workflows-lib` feeds it straight into
`run-tests`, which branches on ansible, python, nodejs, go, rust, java, docker
and generic. A change that silently drops a language from that set makes the
consumer run the wrong (or no) test command, which is why each case below pins
the exact value.

Exit code 0 when every case matches, 1 otherwise.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ACTION = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "actions"
    / "detect-technology"
    / "action.yml"
)

# A galaxy.yml as produced by `ansible-galaxy collection init`: notably no
# `type:` field, which is why detection must key on the file's presence.
GALAXY_YML = (
    "namespace: testns\nname: testcol\nversion: 1.0.0\nreadme: README.md\n"
    "authors:\n  - Test\ndescription: Test collection\nlicense:\n  - MIT\n"
    "dependencies: {}\nrepository: https://example.com\nbuild_ignore: []\n"
)

# fixture name -> (files to create, expected outputs)
CASES: dict[str, tuple[dict[str, str], dict[str, str]]] = {
    "nodejs": ({"package.json": "{}"}, {"primary": "nodejs", "nodejs": "package.json"}),
    "ansible-collection": (
        {"galaxy.yml": GALAXY_YML},
        {"primary": "ansible", "ansible-collection": "galaxy.yml"},
    ),
    "python": ({"pyproject.toml": ""}, {"primary": "python", "python": "pyproject.toml"}),
    "go": ({"go.mod": ""}, {"primary": "go", "go": "go.mod"}),
    "rust": ({"Cargo.toml": ""}, {"primary": "rust", "rust": "Cargo.toml"}),
    "java": ({"pom.xml": ""}, {"primary": "java", "java": "pom.xml"}),
    "docker": ({"Dockerfile": ""}, {"primary": "docker", "container": "Dockerfile"}),
    "docker-compose": (
        {"Dockerfile": "", "docker-compose.yml": ""},
        {"primary": "docker"},
    ),
    "helm": ({"Chart.yml": ""}, {"primary": "generic", "helm": "Chart.yml"}),
    "generic-makefile": ({"Makefile": ""}, {"primary": "generic", "generic": "Makefile"}),
    "empty": ({}, {"primary": "generic", "count": "0"}),
    # ansible outranks every other signal, matching the precedence the consumer
    # previously relied on from its own local detector
    "ansible-beats-python": (
        {"galaxy.yml": GALAXY_YML, "pyproject.toml": "", "package.json": "{}"},
        {"primary": "ansible", "count": "3"},
    ),
    "python-beats-nodejs": (
        {"pyproject.toml": "", "package.json": "{}"},
        {"primary": "python", "count": "2"},
    ),
    "execution-environment": (
        {"execution-environment.yml": ""},
        {"primary": "generic", "ansible-execution-environment": "execution-environment.yml"},
    ),
}


def load_script() -> str:
    step = yaml.safe_load(ACTION.read_text())["runs"]["steps"][0]
    return step["run"].replace("${{ inputs.fail-on-missing }}", "false")


def run_against(script: str, files: dict[str, str]) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, content in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        out = root / ".out"
        out.write_text("")
        result = subprocess.run(
            ["bash", "-c", script],
            cwd=root,
            env={"GITHUB_OUTPUT": str(out), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"script failed: {result.stderr.strip()}")
        parsed = {}
        for line in out.read_text().splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                parsed[key.strip()] = value.strip()
        return parsed


def main() -> int:
    script = load_script()
    failures: list[str] = []

    for name, (files, expected) in CASES.items():
        try:
            actual = run_against(script, files)
        except Exception as exc:  # noqa: BLE001 - report, do not abort the suite
            failures.append(f"{name}: {exc}")
            continue
        for key, want in expected.items():
            got = actual.get(key, "")
            if got != want:
                failures.append(f"{name}: {key} expected {want!r}, got {got!r}")

    if failures:
        print(f"detection FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"detection OK ({len(CASES)} fixtures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
