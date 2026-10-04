#!/usr/bin/env python3
"""Regression tests for bump-version as the single version authority.

The release contract used to accept an empty version and let github-tag-action
derive one from conventional commits. That created a second authority: a repo
could release a version nothing had bumped, and the tag would disagree with the
file consumers read. The contract now requires an explicit version, and these
assertions exist so that capability cannot quietly come back.

Checked structurally, because the derivation was never local code -- it was
`custom_tag` being empty, which is invisible in a diff of this repository.

Exit code 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT = ROOT / ".github" / "workflows" / "release-github.yml"
ACTION = ROOT / ".github" / "actions" / "release-github" / "action.yml"
ENTRYPOINT = ROOT / ".github" / "workflows" / "release.yml"
VERSION_FILE = ROOT / "VERSION"


def main() -> int:
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        if not condition:
            failures.append(f"{label}{f' -- {detail}' if detail else ''}")

    contract = yaml.safe_load(CONTRACT.read_text())
    action = yaml.safe_load(ACTION.read_text())
    entry = yaml.safe_load(ENTRYPOINT.read_text())

    # 1. The contract must not accept an empty version.
    c_version = contract[True]["workflow_call"]["inputs"]["version"]
    check("contract version is required", c_version.get("required") is True, str(c_version))
    check(
        "contract version has no default",
        "default" not in c_version,
        f"default={c_version.get('default')!r} would re-enable derivation",
    )

    # 2. Same at the implementation boundary.
    a_version = action["inputs"]["version"]
    check("action version is required", a_version.get("required") is True, str(a_version))
    check(
        "action version has no default",
        "default" not in a_version,
        f"default={a_version.get('default')!r}",
    )

    # 3. custom_tag must be fed the required version. An empty custom_tag is
    # precisely what makes github-tag-action derive from commit messages.
    tag_steps = [s for s in action["runs"]["steps"] if s.get("id") == "tag"]
    check("tag step exists", len(tag_steps) == 1, f"found {len(tag_steps)}")
    if tag_steps:
        custom_tag = (tag_steps[0].get("with") or {}).get("custom_tag", "")
        check(
            "custom_tag is wired to the version input",
            custom_tag.replace(" ", "") == "${{inputs.version}}",
            f"custom_tag={custom_tag!r}",
        )

    # 4. VERSION is the artifact bump-version owns, so it must exist and be clean.
    check("VERSION file exists", VERSION_FILE.is_file())
    if VERSION_FILE.is_file():
        raw = VERSION_FILE.read_text().strip()
        check(
            "VERSION is a clean release version",
            re.fullmatch(r"\d+\.\d+\.\d+", raw) is not None,
            f"VERSION={raw!r}",
        )

    # 5. The self-release entrypoint reads that file instead of deriving.
    entry_text = ENTRYPOINT.read_text()
    check(
        "entrypoint reads the VERSION file",
        re.search(r"<\s*VERSION", entry_text) is not None,
        "expected a redirection from VERSION, not a hardcoded or derived value",
    )
    dispatch = entry[True]
    check(
        "entrypoint no longer accepts a manual version override",
        "inputs" not in (dispatch.get("workflow_dispatch") or {}),
        f"workflow_dispatch={dispatch.get('workflow_dispatch')!r}",
    )

    release_job = entry["jobs"]["release"]
    check(
        "entrypoint passes the resolved version to the contract",
        release_job["with"]["version"] == "${{ needs.resolve.outputs.version }}",
        f"version={release_job['with']['version']!r}",
    )
    check(
        "entrypoint resolves before releasing",
        release_job.get("needs") == "resolve",
        f"needs={release_job.get('needs')!r}",
    )

    if failures:
        print(f"version authority FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("version authority OK (11 checks: contract, action, tag wiring, VERSION, entrypoint)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
