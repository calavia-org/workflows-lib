#!/usr/bin/env python3
"""Invariant test for the run-tests composite action's JUnit report wiring.

The CI Gate publishes test results from JUnit XML. Python/Ansible projects run
through tox, and tox only forwards pytest flags placed after a literal `--`
(its {posargs}); a bare `--junitxml` is swallowed by tox, so no report is
written and the Gate has nothing to publish. This suite replays the shipped
"Run unit tests" step against a stubbed interpreter and asserts the JUnit flag
reaches pytest in every python/ansible path.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / ".github/actions/run-tests/action.yml"
STEP_NAME = "Run unit tests"
EXPR = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
JUNIT_FLAG = "--junitxml=test-results.xml"
TOX_SEPARATOR = f"-- {JUNIT_FLAG}"
STUB = '#!/usr/bin/env bash\necho "$@" >> invocation.txt\n'


def unit_test_script() -> str:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("name") == STEP_NAME:
            return step["run"]
    raise AssertionError(f"run-tests is missing its {STEP_NAME!r} step")


def render(command: str, technology: str) -> str:
    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key == "steps.test-cmd.outputs.command":
            return command
        if key == "inputs.technology":
            return technology
        if key == "inputs.test-report-format":
            return "junit"
        if key == "inputs.coverage-report":
            return "false"
        return ""

    return EXPR.sub(substitute, unit_test_script())


def invoke(command: str, technology: str) -> str:
    """Run the step with `python`/`pytest` stubbed; return the recorded argv."""
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        stub_dir = workdir / "bin"
        stub_dir.mkdir()
        for tool in ("python", "pytest"):
            stub = stub_dir / tool
            stub.write_text(STUB)
            stub.chmod(0o755)

        env = dict(os.environ)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
        env["GITHUB_OUTPUT"] = str(workdir / "github_output")

        result = subprocess.run(
            ["bash", "-c", render(command, technology)],
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return (workdir / "invocation.txt").read_text()


def test_tox_forwards_junit_after_double_dash():
    argv = invoke("python -m tox --conf tox.ini", "python")
    assert TOX_SEPARATOR in argv, (
        "the tox path must forward --junitxml after a literal `--`, otherwise "
        f"tox swallows it and no report is produced; recorded argv: {argv!r}"
    )


def test_ansible_tox_forwards_junit_after_double_dash():
    argv = invoke("python -m tox --ansible --conf tox.ini", "ansible")
    assert TOX_SEPARATOR in argv, (
        f"the ansible/tox path must forward --junitxml after `--`; recorded argv: {argv!r}"
    )


def test_direct_pytest_gets_bare_junit_flag():
    argv = invoke("pytest", "python")
    assert JUNIT_FLAG in argv, (
        f"a non-tox python path must append --junitxml directly; recorded argv: {argv!r}"
    )
    assert TOX_SEPARATOR not in argv, (
        "a direct pytest invocation must not inject tox's `--` separator"
    )


def test_all():
    test_tox_forwards_junit_after_double_dash()
    test_ansible_tox_forwards_junit_after_double_dash()
    test_direct_pytest_gets_bare_junit_flag()
    print("\nrun-tests-junit OK")


if __name__ == "__main__":
    test_all()
