#!/usr/bin/env python3
"""Invariant checks for the SAST/SCA/secret scanner composite actions.

Each scanner action must expose the same minimal contract (inputs, outputs,
SARIF upload) and must install/run a specific open-source CLI tool. These
checks guard against accidentally breaking the security scanning surface when
refactoring the composite actions.

Also guards the `security` job wiring in reusable-ci.yml: one matrix leg per
scanner action, with fail-fast disabled so a red scanner cannot cancel its
siblings' SARIF uploads.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

WF = ".github/workflows/reusable-ci.yml"

SCANNERS = {
    "scan-secrets": {
        "tool": "trufflehog",
        "install_patterns": ("trufflesecurity/trufflehog",),
    },
    "scan-sast": {
        "tool": "semgrep",
        "install_patterns": ("pip install", "semgrep"),
    },
    "scan-misconfig": {
        "tool": "trivy",
        "install_patterns": ("aquasecurity/trivy",),
    },
    "scan-dependencies": {
        "tool": "osv-scanner",
        "install_patterns": ("google/osv-scanner",),
    },
}

LEG_FOR_ACTION = {name: name.removeprefix("scan-") for name in SCANNERS}

REQUIRED_INPUTS = {"path", "severity", "upload-sarif", "github-token", "extra-args"}
REQUIRED_OUTPUTS = {"sarif-path", "findings"}
UPLOAD_ACTION = "github/codeql-action/upload-sarif@v4"


def load_action(name: str) -> dict:
    path = Path(f".github/actions/{name}/action.yml")
    if not path.exists():
        raise SystemExit(f"missing action file: {path}")
    return yaml.safe_load(path.read_text())


def step_named(doc: dict, name: str) -> dict | None:
    for step in doc.get("runs", {}).get("steps", []):
        if step.get("name") == name:
            return step
    return None


def step_with_id(doc: dict, step_id: str) -> dict | None:
    for step in doc.get("runs", {}).get("steps", []):
        if step.get("id") == step_id:
            return step
    return None


def check_action(name: str, spec: dict) -> list[str]:
    errors: list[str] = []
    doc = load_action(name)

    for key in ("name", "description"):
        if not isinstance(doc.get(key), str) or not doc[key].strip():
            errors.append(f"{name}: missing or empty '{key}'")

    inputs = set(doc.get("inputs", {}).keys())
    missing_inputs = REQUIRED_INPUTS - inputs
    if missing_inputs:
        errors.append(f"{name}: missing inputs {sorted(missing_inputs)}")

    outputs = set(doc.get("outputs", {}).keys())
    missing_outputs = REQUIRED_OUTPUTS - outputs
    if missing_outputs:
        errors.append(f"{name}: missing outputs {sorted(missing_outputs)}")

    for output_name in REQUIRED_OUTPUTS:
        out = doc.get("outputs", {}).get(output_name)
        if isinstance(out, dict) and out.get("value", "").startswith(
            "${{ steps.scan.outputs."
        ):
            continue
        errors.append(
            f"{name}: output '{output_name}' must derive from steps.scan.outputs"
        )

    install_step = doc.get("runs", {}).get("steps", [{}])[0]
    run = install_step.get("run", "")
    if not any(pattern in run for pattern in spec["install_patterns"]):
        errors.append(
            f"{name}: install step does not reference expected patterns {spec['install_patterns']}"
        )

    scan_step = step_with_id(doc, "scan")
    if scan_step is None:
        errors.append(f"{name}: missing step with id 'scan'")
    else:
        run = scan_step.get("run", "")
        if spec["tool"] not in run.lower():
            errors.append(f"{name}: scan step does not invoke {spec['tool']}")
        if "sarif" not in run.lower():
            errors.append(f"{name}: scan step does not produce SARIF output")

    upload_step = step_named(doc, "Upload SARIF")
    if upload_step is None:
        errors.append(f"{name}: missing 'Upload SARIF' step")
    elif upload_step.get("uses") != UPLOAD_ACTION:
        errors.append(f"{name}: Upload SARIF must use {UPLOAD_ACTION}")

    return errors


def check_workflow_wiring() -> list[str]:
    errors: list[str] = []
    doc = yaml.safe_load(Path(WF).read_text())
    job = (doc.get("jobs") or {}).get("security")
    if job is None:
        return [f"{WF}: missing 'security' job"]

    strategy = job.get("strategy") or {}
    legs = (strategy.get("matrix") or {}).get("scanner")
    expected_legs = list(LEG_FOR_ACTION.values())
    if legs != expected_legs:
        errors.append(
            f"security: matrix.scanner == {legs!r}, expected {expected_legs!r}"
        )
    if strategy.get("fail-fast") is not False:
        errors.append(
            "security: strategy.fail-fast must be false so a red scanner "
            "cannot cancel its siblings"
        )

    perms = job.get("permissions") or {}
    if perms.get("security-events") != "write":
        errors.append("security: permissions must include security-events: write")

    for action, leg in LEG_FOR_ACTION.items():
        uses = f"$/.github/actions/{action}"
        step = next(
            (s for s in (job.get("steps") or []) if s.get("uses") == uses),
            None,
        )
        if step is None:
            errors.append(f"security: no step uses {uses}")
            continue
        cond = str(step.get("if", ""))
        if f"matrix.scanner == '{leg}'" not in cond:
            errors.append(
                f"security: {action} step if must gate on "
                f"matrix.scanner == '{leg}': {cond!r}"
            )
        if f"inputs.scan-{leg}" not in cond:
            errors.append(
                f"security: {action} step if must gate on inputs.scan-{leg}: {cond!r}"
            )
    return errors


def main() -> int:
    all_errors: list[str] = []
    for name, spec in SCANNERS.items():
        all_errors.extend(check_action(name, spec))
    all_errors.extend(check_workflow_wiring())

    if all_errors:
        print("scanner action invariants FAILED:")
        for error in all_errors:
            print(f"  - {error}")
        return 1

    print(f"scanner action invariants OK ({len(SCANNERS)} actions)")
    return 0


def test_main():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
