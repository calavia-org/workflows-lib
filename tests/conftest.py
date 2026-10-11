"""Shared helpers for invariant test suites."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent


def repo_path(*parts: str) -> Path:
    """Return a path relative to the repository root."""
    return REPO.joinpath(*parts)


def load_yaml(path: str | Path) -> dict:
    """Load a YAML file from a path relative to the repo root."""
    return yaml.safe_load(repo_path(path).read_text())


def step_script_by_id(action_path: str, step_id: str) -> str:
    """Extract the run block of a composite action step by id."""
    data = load_yaml(action_path)
    for step in data["runs"]["steps"]:
        if step.get("id") == step_id:
            return step["run"]
    raise KeyError(f"step {step_id!r} not found in {action_path}")


def workflow_jobs(workflow_path: str) -> dict:
    """Return the jobs dictionary from a workflow file."""
    return load_yaml(workflow_path)["jobs"]
