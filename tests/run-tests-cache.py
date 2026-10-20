#!/usr/bin/env python3
"""Invariant tests for the tox environment cache wiring.

run-tests restores `.tox` before running tox, keyed on the dependency file
hashes (exact key, no restore-keys) plus OS, arch, Python version and the
unit|integration phase. reusable-ci must pass `cache-enabled` to EVERY
run-tests call site - build included - so the single cache toggle disables
all caching, not just the built-in setup-* caches.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github/workflows/reusable-ci.yml"
ACTION = REPO / ".github/actions/run-tests/action.yml"
CACHE_STEP = "Cache tox environments"
RUN_TESTS = "run-tests"

KEY_MARKERS = [
    "${{ runner.os }}",
    "${{ runner.arch }}",
    "${{ inputs.python-version }}",
    "inputs.run-unit-tests == 'true' && 'unit' || 'integration'",
    "hashFiles",
    "inputs.tox-ini",
]


def jobs() -> dict:
    return yaml.safe_load(CI.read_text())["jobs"]


def cache_step() -> dict:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("name") == CACHE_STEP:
            return step
    raise AssertionError(f"run-tests is missing its {CACHE_STEP!r} step")


def run_tests_call_sites() -> list[dict]:
    sites = []
    for job in jobs().values():
        for step in job.get("steps", []):
            if step.get("uses", "").endswith(f"/{RUN_TESTS}"):
                sites.append(step)
    return sites


def test_cache_step_exists_with_tox_path():
    step = cache_step()
    assert step["with"]["path"] == ".tox", (
        "the cache must target the tox env dirs, the dominant per-leg cost; "
        f"path: {step['with'].get('path')!r}"
    )


def test_cache_step_is_gated_on_the_toggle_and_a_test_phase():
    condition = cache_step()["if"]
    assert "inputs.cache-enabled == 'true'" in condition, (
        "the step must honor the single cache-enabled toggle so consumers can "
        f"turn caching off; if: {condition!r}"
    )
    assert (
        "run-unit-tests == 'true'" in condition
        and "run-integration-tests == 'true'" in condition
    ), (
        "the step must only run when a test phase actually runs, otherwise it "
        f"would cache an empty .tox; if: {condition!r}"
    )


def test_cache_key_pins_every_invalidation_component():
    key = cache_step()["with"]["key"]
    for marker in KEY_MARKERS:
        assert marker in key, (
            "the key must stay per-OS, per-arch, per-Python and per-phase and "
            f"hash the dependency files; missing {marker!r}; key: {key!r}"
        )


def test_cache_step_has_no_restore_keys():
    step = cache_step()
    assert "restore-keys" not in step["with"], (
        "invalidation must be mechanism-independent (file hashes); a "
        "restore-keys prefix would serve an env restored from before a "
        f"dependency change; with: {sorted(step['with'])}"
    )


def test_cache_step_uses_pinned_actions_cache():
    uses = cache_step()["uses"]
    assert uses.startswith("actions/cache@"), (
        f"the cache step must use actions/cache; uses: {uses!r}"
    )
    assert not uses.endswith("@main") and not uses.endswith("@master"), (
        f"the cache action must be pinned to a released ref, not a branch; uses: {uses!r}"
    )


def setup_python_step() -> dict:
    data = yaml.safe_load(ACTION.read_text())
    for step in data["runs"]["steps"]:
        if step.get("name") == "Setup Python":
            return step
    raise AssertionError("run-tests is missing its 'Setup Python' step")


def test_setup_python_pip_cache_hashes_tox_and_lock_files():
    path = setup_python_step()["with"]["cache-dependency-path"]
    assert "${{ inputs.tox-ini }}" in path, (
        "setup-python must hash the tox conf, otherwise a tox-only consumer "
        f"has no matching dependency file and gets no pip cache; path: {path!r}"
    )
    for name in ("pyproject.toml", "poetry.lock", "requirements*.txt"):
        assert name in path, (
            "the pip cache key must cover the usual lock/dep files so a warm "
            f"cache is restored on dependency-stable runs; missing {name!r}; "
            f"path: {path!r}"
        )


def test_every_run_tests_call_site_passes_cache_enabled():
    sites = run_tests_call_sites()
    assert sites, "reusable-ci must call run-tests from at least one job"
    for step in sites:
        assert "cache-enabled" in step["with"], (
            "every run-tests call site must forward cache-enabled so the "
            "toggle governs all caching; a call site that omits it silently "
            f"caches under cache-enabled: false; with: {sorted(step['with'])}"
        )


def test_all():
    test_cache_step_exists_with_tox_path()
    test_cache_step_is_gated_on_the_toggle_and_a_test_phase()
    test_cache_key_pins_every_invalidation_component()
    test_cache_step_has_no_restore_keys()
    test_cache_step_uses_pinned_actions_cache()
    test_setup_python_pip_cache_hashes_tox_and_lock_files()
    test_every_run_tests_call_site_passes_cache_enabled()
    print("\nrun-tests-cache OK")


if __name__ == "__main__":
    test_all()
