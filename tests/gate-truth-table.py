#!/usr/bin/env python3
"""Verify the required `Test` gate in pr-check-and-test.yml.

The gate logic is EXTRACTED FROM THE WORKFLOW and executed with bash, so this
tests the shipped shell rather than a transcription of it. Job `if` expressions
are likewise read from the workflow and evaluated.

Two GitHub rules are modelled:
  1. A job whose dependency did not succeed is auto-skipped UNLESS its `if`
     contains a status function (`always()`).
  2. `skipped` is therefore ambiguous - a failed `build` reaches the gate as
     `unit=skipped`, indistinguishable from "tests disabled". The gate must
     disambiguate with explicit BUILD_RESULT / PACKAGE_RESULT checks.
"""
import os
import re
import subprocess
import sys
import tempfile

import yaml

WF = ".github/workflows/pr-check-and-test.yml"
STATUS_OK = {"success", "skipped"}
GATE_STEP = "Verify required tests passed"


def load():
    with open(WF) as fh:
        doc = yaml.safe_load(fh)
    inputs = {}
    for k, v in (doc.get(True) or doc.get("on"))["workflow_call"]["inputs"].items():
        inputs[k] = v.get("default", False)
    return doc["jobs"], inputs


def needs_of(jobs, name):
    n = jobs[name].get("needs") or []
    return [n] if isinstance(n, str) else list(n)


def topo(jobs):
    order, seen, stack = [], set(), set()

    def visit(n, path):
        if n in stack:
            raise SystemExit(f"cycle: {path + [n]}")
        if n in seen:
            return
        stack.add(n)
        for m in needs_of(jobs, n):
            visit(m, path + [n])
        stack.discard(n)
        seen.add(n)
        order.append(n)

    for n in jobs:
        visit(n, [])
    return order


def eval_if(cond, results, inputs, base_ref):
    if not cond:
        return True
    e = re.sub(r"\$\{\{(.*?)\}\}", r"\1", cond, flags=re.S).strip()
    e = e.replace("&&", " and ").replace("||", " or ")
    e = re.sub(r"inputs\.([A-Za-z0-9_-]+)", lambda m: repr(inputs.get(m.group(1))), e)
    e = re.sub(
        r"needs\.([A-Za-z0-9_-]+)\.result",
        lambda m: repr(results.get(m.group(1), "")),
        e,
    )
    e = e.replace("always()", "True")
    e = re.sub(r"github\.base_ref", repr(base_ref), e)
    e = re.sub(r"startsWith\(([^,]+),\s*'([^']*)'\)", r"\1.startswith('\2')", e)
    try:
        return bool(eval(e, {"__builtins__": {}}, {}))
    except Exception as exc:
        raise SystemExit(f"cannot evaluate {cond!r} -> {e!r}: {exc}")


def has_status_fn(cond):
    return bool(cond) and any(f in cond for f in ("always()", "success()", "failure()"))


def gate_script(jobs):
    """Pull the real bash out of the gate step."""
    for step in jobs["report"]["steps"]:
        if step.get("name") == GATE_STEP:
            return step["run"], sorted((step.get("env") or {}).keys())
    raise SystemExit(f"gate step {GATE_STEP!r} not found in report job")


def run_gate(script, results, names):
    """Execute the shipped gate with the given job results. Pass == exit 0."""
    env = dict(os.environ)
    for n in names:
        env[n] = results.get(n.lower().replace("_result", ""), "")
    p = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    return p.returncode == 0, p.stdout.strip()


def run(jobs, defaults, fail_jobs, base_ref="main", prerelease=False, script=None, names=None):
    results = {}
    for name in topo(jobs):
        cond = jobs[name].get("if")
        inputs = dict(defaults, **{"prerelease-enabled": prerelease})
        blocked = any(results.get(d) != "success" for d in needs_of(jobs, name))
        if blocked and not has_status_fn(cond):
            results[name] = "skipped"
            continue
        if not eval_if(cond, results, inputs, base_ref):
            results[name] = "skipped"
            continue
        results[name] = "failure" if name in fail_jobs else "success"
        if name == "report" and results[name] == "success" and script:
            ok, _ = run_gate(script, results, names)
            if not ok:
                results[name] = "failure"
    return results


def main():
    jobs, defaults = load()
    script, names = gate_script(jobs)

    expected = {
        "unit": ["detect", "pre-commit", "build"],
        "integration": ["detect", "package"],
        "report": ["unit", "integration", "build", "package"],
        "pre-release": ["report"],
    }
    for job, deps in expected.items():
        if needs_of(jobs, job) != deps:
            print(f"FAIL drift: {job}.needs == {needs_of(jobs, job)}, expected {deps}")
            return 1
    for job in ("unit", "integration"):
        if not has_status_fn(jobs[job].get("if")):
            print(f"FAIL: {job}.if lost always()")
            return 1
    # Every prerequisite the graph wires into the gate must be asserted by the
    # gate itself, otherwise a red prerequisite hides behind a skip.
    blocks = re.findall(r"if \[(.*?)\]; then(.*?)fi", script, re.S)
    for token in ("UNIT_RESULT", "INTEGRATION_RESULT", "BUILD_RESULT", "PACKAGE_RESULT"):
        if token not in script:
            print(f"FAIL: gate script never reads {token}")
            return 1
        asserted = any(
            token in cond and "FAILED=1" in body for cond, body in blocks
        )
        if not asserted:
            print(f"FAIL: {token} is read but never sets FAILED=1")
            return 1

    ok_all = True

    def scenario(label, fail_jobs, expect_pass, **over):
        nonlocal ok_all
        results = run(jobs, dict(defaults, **over), fail_jobs, script=script, names=names)
        passed, out = run_gate(script, results, names)
        good = passed == expect_pass
        ok_all &= good
        print(
            f"  {'ok ' if good else 'FAIL'} {label:<36} Test "
            f"{'passes' if passed else 'fails'} (expected "
            f"{'pass' if expect_pass else 'fail'})"
        )
        if not good:
            print("        " + out.replace("\n", "\n        "))

    print("a red prerequisite must turn the gate red:")
    for job in ("unit", "integration", "build", "package", "pre-commit"):
        scenario(f"{job} fails", {job}, expect_pass=False, **{"run-package": True})

    print("\noptional stages disabled must stay green:")
    scenario("integration disabled", set(), True, run_integration_tests=False)
    scenario("build disabled", set(), True, run_build=False)
    scenario("package disabled", set(), True, run_package=False)
    scenario("all enabled", set(), True, **{"run-package": True})

    print("\npre-release only on release/* and only behind a green gate:")
    for label, base, fail, want in (
        ("base=main", "main", set(), "skipped"),
        ("base=release/*", "release/1.8.0", set(), "success"),
        ("red gate", "release/1.8.0", {"unit"}, "skipped"),
    ):
        r = run(jobs, dict(defaults, **{"run-package": True}), fail, base, prerelease=True, script=script, names=names)
        good = r["pre-release"] == want
        ok_all &= good
        print(f"  {'ok ' if good else 'FAIL'} {label:<36} pre-release={r['pre-release']} (expected {want})")

    print("\nall scenarios correct" if ok_all else "\nscenario errors found")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
