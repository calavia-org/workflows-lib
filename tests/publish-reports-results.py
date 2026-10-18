#!/usr/bin/env python3
"""Invariant test for publish-reports' graceful skip when no results exist.

EnricoMi/publish-unit-test-result-action warns loudly when its file globs match
nothing, which pollutes the CI log for technologies that emit no JUnit XML.
This suite replays the shipped "Detect test result files" step and asserts it
sets `found` and emits a ::notice:: (never a ::warning::) instead, and that the
publish step is gated on that signal.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / ".github/actions/publish-reports/action.yml"
EXPR = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
RESULTS_EXPR = "inputs.test-results-path"
# actions/download-artifact inputs (v8). Notably it has NO `if-no-files-found`
# (that is upload-artifact only) and needs none: a pattern with zero matches
# succeeds with "Found 0 artifact(s)", it does not fail.
DOWNLOAD_ARTIFACT_INPUTS = {
    "name",
    "artifact-ids",
    "path",
    "pattern",
    "merge-multiple",
    "github-token",
    "repository",
    "run-id",
    "skip-decompress",
    "digest-mismatch",
}


def action_steps() -> list[dict]:
    return yaml.safe_load(ACTION.read_text())["runs"]["steps"]


def step_by_id(step_id: str) -> dict:
    for step in action_steps():
        if step.get("id") == step_id:
            return step
    raise AssertionError(f"publish-reports has no step with id {step_id!r}")


def step_by_name(name: str) -> dict:
    for step in action_steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"publish-reports has no step named {name!r}")


def resolve(value: str, results_path: Path) -> str:
    return EXPR.sub(
        lambda match: str(results_path) if match.group(1) == RESULTS_EXPR else "",
        value,
    )


def detect_script() -> str:
    return step_by_id("detect-results")["run"]


def detect_env(results_path: Path) -> dict[str, str]:
    raw = step_by_id("detect-results").get("env") or {}
    return {key: resolve(str(value), results_path) for key, value in raw.items()}


def run_detect(prepare) -> tuple[str, str]:
    """prepare(results: Path) -> None; returns (found, stdout)."""
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        results = workdir / "test-results"
        prepare(results)

        output = workdir / "github_output"
        output.write_text("")
        env = dict(os.environ)
        env["GITHUB_OUTPUT"] = str(output)
        env.update(detect_env(results))

        result = subprocess.run(
            ["bash", "-c", detect_script()],
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

        found = ""
        for line in output.read_text().splitlines():
            if line.startswith("found="):
                found = line.split("=", 1)[1]
        return found, result.stdout


def _missing(_results: Path) -> None:
    return None


def _empty_dir(results: Path) -> None:
    results.mkdir(parents=True)


def _with_xml(results: Path) -> None:
    results.mkdir(parents=True)
    (results / "test-results.xml").write_text("<testsuite/>")


def test_missing_dir_skips_with_notice():
    found, stdout = run_detect(_missing)
    assert found == "false", f"expected found=false for a missing dir, got {found!r}"
    assert "::notice::" in stdout, "a missing results dir must skip via ::notice::"
    assert "::warning::" not in stdout, "skipping must never emit a ::warning::"


def test_empty_dir_skips_with_notice():
    found, stdout = run_detect(_empty_dir)
    assert found == "false", f"expected found=false for an empty dir, got {found!r}"
    assert "::notice::" in stdout, "an empty results dir must skip via ::notice::"
    assert "::warning::" not in stdout, "skipping must never emit a ::warning::"


def test_present_xml_enables_publishing():
    found, stdout = run_detect(_with_xml)
    assert found == "true", (
        f"expected found=true when a JUnit XML exists, got {found!r}"
    )
    assert "::notice::" not in stdout, (
        "a run with results must not print the skip notice"
    )


def test_publish_step_is_gated_on_detection():
    condition = step_by_name("Publish test results").get("if", "")
    assert "steps.detect-results.outputs.found == 'true'" in condition, (
        "the publish step must be gated on the detect-results step so an empty "
        f"run skips quietly instead of warning; got: {condition!r}"
    )


def test_download_step_passes_only_supported_inputs():
    with_ = step_by_name("Download test artifacts").get("with") or {}
    unsupported = set(with_) - DOWNLOAD_ARTIFACT_INPUTS
    assert not unsupported, (
        f"download-artifact does not support {sorted(unsupported)}; supported "
        f"inputs are {sorted(DOWNLOAD_ARTIFACT_INPUTS)}"
    )


def test_detect_step_has_no_run_interpolation():
    script = detect_script()
    assert not EXPR.search(script), (
        "detect-results must not interpolate ${{ ... }} directly in run: "
        "(Semgrep run-shell-injection); pass values through env: instead"
    )


def test_all():
    test_missing_dir_skips_with_notice()
    test_empty_dir_skips_with_notice()
    test_present_xml_enables_publishing()
    test_publish_step_is_gated_on_detection()
    test_download_step_passes_only_supported_inputs()
    test_detect_step_has_no_run_interpolation()
    print("\npublish-reports-results OK")


if __name__ == "__main__":
    test_all()
