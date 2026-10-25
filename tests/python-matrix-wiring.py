#!/usr/bin/env python3
"""Invariant tests for the derived Python test matrix wiring.

detect-technology emits `python-matrix` from the tox env list; reusable-ci
turns it into the unit job's strategy.matrix and passes each version down to
run-tests. The integration job expands the same list unless the consumer
pins `integration-python-matrix`. Ansible repos keep working because
run-tests installs the tox-ansible plugin whenever the resolved conf is a
tox-ansible config, not only when the technology input resolved to
`ansible`.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github/workflows/reusable-ci.yml"
ACTION = REPO / ".github/actions/run-tests/action.yml"
INSTALL_STEP = "Install tox"
EXPRESSION = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
STUB = '#!/usr/bin/env bash\necho "$@" >> invocation.txt\n'


def jobs() -> dict:
    return yaml.safe_load(CI.read_text())["jobs"]


def detect_job() -> dict:
    return jobs()["detect"]


def detect_step() -> dict:
    for step in detect_job()["steps"]:
        if step.get("uses", "").endswith("/detect-technology"):
            return step
    raise AssertionError("detect job must call the detect-technology action")


def unit_run_tests_step() -> dict:
    for step in jobs()["unit"]["steps"]:
        if step.get("uses", "").endswith("/run-tests"):
            return step
    raise AssertionError("unit job must call the run-tests action")


def integration_run_tests_step() -> dict:
    for step in jobs()["integration"]["steps"]:
        if step.get("uses", "").endswith("/run-tests"):
            return step
    raise AssertionError("integration job must call the run-tests action")


def install_tox_script() -> str:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("name") == INSTALL_STEP:
            return step["run"]
    raise AssertionError(f"run-tests is missing its {INSTALL_STEP!r} step")


def test_detect_exposes_python_matrix():
    outputs = detect_job()["outputs"]
    assert (
        outputs.get("python-matrix") == "${{ steps.detect.outputs.python-matrix }}"
    ), (
        "the detect job must surface python-matrix or the unit matrix has "
        f"nothing to expand; outputs: {sorted(outputs)}"
    )


def test_detect_step_forwards_matrix_inputs():
    with_ = detect_step()["with"]
    assert with_.get("tox-ini") == "${{ inputs.tox-ini }}", (
        "detect must read the same tox conf the unit tests will run against, "
        f"otherwise the matrix and run-tests disagree; with: {with_}"
    )
    assert with_.get("python-version") == "${{ inputs.python-version }}", (
        "the single-version fallback must come from the workflow input so a "
        f"consumer override is honored; with: {with_}"
    )


def test_unit_matrix_derives_from_detect_output():
    matrix = jobs()["unit"]["strategy"]["matrix"]
    assert (
        matrix.get("python-version")
        == "${{ fromJSON(needs.detect.outputs.python-matrix) }}"
    ), (
        "unit must expand its strategy from the detect output; an empty or "
        f"hard-coded matrix skips the declared tox versions; matrix: {matrix}"
    )


def test_unit_passes_matrix_version_to_run_tests():
    version = unit_run_tests_step()["with"]["python-version"]
    assert version == "${{ matrix.python-version }}", (
        "each matrix leg must test its own Python version, not the workflow "
        f"default; run-tests with.python-version: {version}"
    )


def test_integration_matrix_input_is_opt_in_pin():
    inputs = yaml.safe_load(CI.read_text())["on"]["workflow_call"]["inputs"]
    spec = inputs.get("integration-python-matrix")
    assert spec is not None, (
        "integration-python-matrix must exist so consumers can pin the "
        f"integration fan-out; inputs: {sorted(inputs)}"
    )
    assert spec.get("default") == "" and spec.get("required") is False, (
        "the pin must default to empty (meaning: same list as unit) so "
        f"existing callers keep their fan-out unchanged; spec: {spec}"
    )


def test_integration_matrix_is_planned():
    matrix = jobs()["integration"]["strategy"]["matrix"]
    assert matrix == "${{ fromJSON(needs.integration-plan.outputs.matrix) }}", (
        "integration must expand from the integration-plan job so molecule "
        "scenarios can override the python matrix without complex inline "
        f"expressions; matrix: {matrix}"
    )


def test_integration_plan_falls_back_to_detect_output():
    plan = jobs()["integration-plan"]
    step = next(
        s for s in plan["steps"] if s.get("id") == "matrix"
    )
    env = step.get("env", {})
    run = step["run"]
    assert env.get("PYTHON_MATRIX") == "${{ needs.detect.outputs.python-matrix }}", (
        "integration-plan must receive the detect python matrix as input "
        f"env; env: {env}"
    )
    assert "INTEGRATION_PYTHON_MATRIX" in env, (
        "integration-plan must receive the consumer python matrix pin; "
        f"env: {env}"
    )
    assert "python-version" in run, (
        "integration-plan must emit a python-version matrix when no "
        f"molecule scenarios are found; run: {run}"
    )


def test_integration_passes_matrix_version_to_run_tests():
    version = integration_run_tests_step()["with"]["python-version"]
    assert version == "${{ matrix.python-version || inputs.python-version }}", (
        "each integration leg must resolve its own Python when the matrix "
        "includes python-version (scenario-only matrices fall back to the "
        "workflow default); run-tests with.python-version: {version}"
    )


def render(tox_ini: str, technology: str) -> str:
    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key == "inputs.tox-ini":
            return tox_ini
        if key == "inputs.technology":
            return technology
        return ""

    return EXPRESSION.sub(substitute, install_tox_script())


def invoke(tox_ini: str, technology: str, *, conf_exists: bool) -> list[str]:
    """Run the Install tox step with `python` stubbed; return pip argv lines."""
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        stub_dir = workdir / "bin"
        stub_dir.mkdir()
        python = stub_dir / "python"
        python.write_text(STUB)
        python.chmod(0o755)
        if conf_exists:
            (workdir / tox_ini).write_text("[tox]\nenv_list = py312\n")

        env = dict(os.environ)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
        result = subprocess.run(
            ["bash", "-c", render(tox_ini, technology)],
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        invocations = workdir / "invocation.txt"
        lines = invocations.read_text().splitlines() if invocations.exists() else []
        return [line for line in lines if line]


def test_ansible_technology_installs_plugin():
    argv = invoke("tox.ini", "ansible", conf_exists=True)
    assert any("tox-ansible" in line.split() for line in argv), (
        f"technology=ansible with a tox conf must install tox-ansible; argv: {argv}"
    )


def test_tox_ansible_conf_installs_plugin_for_python():
    argv = invoke("tox-ansible.ini", "python", conf_exists=True)
    assert any("tox-ansible" in line.split() for line in argv), (
        "a tox-ansible.ini conf must install the plugin even when the "
        f"detected technology is python; argv: {argv}"
    )


def test_plain_tox_conf_skips_plugin():
    argv = invoke("tox.ini", "python", conf_exists=True)
    assert any(line.split()[-1] == "tox" for line in argv), (
        f"technology=python with tox.ini must still install tox; argv: {argv}"
    )
    assert not any("tox-ansible" in line.split() for line in argv), (
        f"a plain tox.ini must not pull in tox-ansible; argv: {argv}"
    )


def test_missing_conf_installs_nothing():
    argv = invoke("tox.ini", "ansible", conf_exists=False)
    assert argv == [], f"without a tox conf nothing may be installed; argv: {argv}"


def test_all():
    test_detect_exposes_python_matrix()
    test_detect_step_forwards_matrix_inputs()
    test_unit_matrix_derives_from_detect_output()
    test_unit_passes_matrix_version_to_run_tests()
    test_integration_matrix_input_is_opt_in_pin()
    test_integration_matrix_is_planned()
    test_integration_plan_falls_back_to_detect_output()
    test_integration_passes_matrix_version_to_run_tests()
    test_ansible_technology_installs_plugin()
    test_tox_ansible_conf_installs_plugin_for_python()
    test_plain_tox_conf_skips_plugin()
    test_missing_conf_installs_nothing()
    print("\npython-matrix-wiring OK")


if __name__ == "__main__":
    test_all()
