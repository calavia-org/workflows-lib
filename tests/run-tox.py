#!/usr/bin/env python3
"""Invariant tests for the run-tox composite action."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / ".github/actions/run-tox/action.yml"
TOX = REPO / "tox.ini"


def action_steps() -> list[dict]:
    data = yaml.safe_load(ACTION.read_text())
    return data["runs"]["steps"]


def test_tox_env_list():
    assert TOX.exists(), "tox.ini is missing"
    text = TOX.read_text()
    assert "py310" in text, "tox.ini must include py310"
    assert "py311" in text, "tox.ini must include py311"
    assert "py312" in text, "tox.ini must include py312"
    print("run-tox OK: tox.ini defines py310, py311, py312")


def test_action_uses_mise():
    steps = action_steps()
    uses = [step.get("uses", "") for step in steps]
    assert any("mise-action" in u for u in uses), "action does not use jdx/mise-action"
    print("run-tox OK: action uses mise tooling")


def test_action_runs_tox():
    steps = action_steps()
    runs = [step.get("run", "") for step in steps]
    assert any("tox" in r for r in runs), "action does not run tox"
    print("run-tox OK: action runs tox")


if __name__ == "__main__":
    test_tox_env_list()
    test_action_uses_mise()
    test_action_runs_tox()
    print("\nrun-tox OK")
