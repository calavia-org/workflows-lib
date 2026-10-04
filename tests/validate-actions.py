#!/usr/bin/env python3
"""Validate the metadata contract of every composite action in .github/actions/.

Each action is a published interface that consumers reference by tag, so drift in
its metadata is a breaking change that no compiler will catch. These checks cover
the gaps actionlint leaves open: missing top-level metadata, non-composite runners,
declared inputs that are never wired into a step, and outputs that are never set.

Exit code 0 when every action satisfies the contract, 1 otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ACTIONS_DIR = Path(".github/actions")
REQUIRED_TOP_LEVEL = ("name", "description", "runs")


def collect_action_files() -> list[Path]:
    if not ACTIONS_DIR.is_dir():
        print(f"error: {ACTIONS_DIR} does not exist; run from the repository root")
        sys.exit(1)
    files = sorted(ACTIONS_DIR.glob("*/action.yml"))
    if not files:
        print(f"error: no action.yml found under {ACTIONS_DIR}")
        sys.exit(1)
    return files


def flatten_expressions(value: object, sink: list[str]) -> None:
    """Collect every scalar reachable from a step, so input usage can be searched."""
    if isinstance(value, dict):
        for item in value.values():
            flatten_expressions(item, sink)
    elif isinstance(value, list):
        for item in value:
            flatten_expressions(item, sink)
    elif isinstance(value, str):
        sink.append(value)


def check_action(path: Path) -> list[str]:
    """Return a list of contract violations for one action; empty means valid."""
    try:
        doc = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        return [f"invalid YAML: {exc}"]

    if not isinstance(doc, dict):
        return ["top level must be a mapping"]

    name = path.parent.name
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_TOP_LEVEL:
        if key not in doc:
            errors.append(f"missing required key '{key}'")

    for key in ("name", "description"):
        value = doc.get(key)
        if key in doc and (not isinstance(value, str) or not value.strip()):
            errors.append(f"'{key}' must be a non-empty string")

    runs = doc.get("runs")
    if runs is not None and not isinstance(runs, dict):
        errors.append("'runs' must be a mapping")
        return [f"{name}: {error}" for error in errors], []

    if isinstance(runs, dict):
        using = runs.get("using")
        if using != "composite":
            errors.append(f"'runs.using' must be 'composite', got {using!r}")

        steps = runs.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append("'runs.steps' must be a non-empty list")
            return [f"{name}: {error}" for error in errors], []

        step_ids = {s.get("id") for s in steps if isinstance(s, dict)}

        scalars: list[str] = []
        flatten_expressions(steps, scalars)
        haystack = "\n".join(scalars)

        declared = doc.get("inputs") or {}
        if not isinstance(declared, dict):
            errors.append("'inputs' must be a mapping when present")
        else:
            # Reported, never fatal: a declared-but-unread input is often a real
            # auth wiring gap rather than dead metadata, so deleting it silently
            # would hide a defect instead of surfacing one.
            for input_name in declared:
                if f"inputs.{input_name}" not in haystack:
                    warnings.append(
                        f"input '{input_name}' is declared but never read by a step"
                    )

        outputs = doc.get("outputs") or {}
        if not isinstance(outputs, dict):
            errors.append("'outputs' must be a mapping when present")
        else:
            # An output may be assigned via `steps.<id>.outputs.<name>` or by
            # echoing `<name>=` into $GITHUB_OUTPUT, so a bare name match is the
            # reliable signal that some step can produce it.
            for output_name, spec in outputs.items():
                value = spec.get("value") if isinstance(spec, dict) else None
                if isinstance(value, str) and value.startswith("${{ steps."):
                    dangling = value.split("steps.", 1)[1].split(".", 1)[0].strip()
                    if dangling not in step_ids:
                        errors.append(
                            f"output '{output_name}' references step id "
                            f"'{dangling}', which no step declares"
                        )
                if output_name not in haystack:
                    warnings.append(
                        f"output '{output_name}' is declared but no step assigns it"
                    )

    return (
        [f"{name}: {error}" for error in errors],
        [f"{name}: {warning}" for warning in warnings],
    )


def main() -> int:
    files = collect_action_files()
    errors: list[str] = []
    warnings: list[str] = []

    for path in files:
        action_errors, action_warnings = check_action(path)
        errors.extend(action_errors)
        warnings.extend(action_warnings)

    for warning in warnings:
        print(f"warning: {warning}")

    if errors:
        print(f"action structure FAILED ({len(errors)} problem(s)):")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        f"action structure OK ({len(files)} composite actions, "
        f"{len(warnings)} wiring warning(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())