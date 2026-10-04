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

import os
import pathlib
import re
import subprocess
import sys
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT = ROOT / ".github" / "workflows" / "release-github.yml"
ACTION = ROOT / ".github" / "actions" / "release-github" / "action.yml"
ENTRYPOINT = ROOT / ".github" / "workflows" / "release.yml"
VERSION_FILE = ROOT / "VERSION"
BUMP_CONTRACT = ROOT / ".github" / "workflows" / "pr-check-and-bump.yml"
BUMP_ACTION = ROOT / ".github" / "actions" / "bump-version" / "action.yml"


def _reader_script() -> str | None:
    """The verbatim shell that resolves the base version from the version file.

    Taken through yaml.safe_load so the text is the same string GitHub runs,
    not a reconstruction of it.
    """
    doc = yaml.safe_load(BUMP_CONTRACT.read_text())
    for step in doc["jobs"]["auto-bump-version"]["steps"]:
        if step.get("name") == "Get base version for bump":
            return step["run"]
    return None


def _resolve(script: str, content: str) -> tuple[int, str | None]:
    """Run the reader over `content` and return (exit code, resolved version)."""
    with tempfile.TemporaryDirectory() as tmp:
        version_file = pathlib.Path(tmp) / "VERSION"
        version_file.write_text(content)
        # The block's last line appends to GITHUB_OUTPUT. Without a real file the
        # redirect fails and, under `bash -e`, every case exits 1.
        output = pathlib.Path(tmp) / "github_output"
        output.write_text("")
        proc = subprocess.run(
            ["bash", "-e", "-c", script],
            env={
                **os.environ,
                "BASE_VERSION_SOURCE": "file",
                "VERSION_FILE": str(version_file),
                "BASE_BRANCH": "main",
                "GITHUB_OUTPUT": str(output),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        resolved = next(
            (
                line.split("=", 1)[1]
                for line in output.read_text().splitlines()
                if line.startswith("version=")
            ),
            None,
        )
        return proc.returncode, resolved


def _bump_script() -> str | None:
    """The verbatim shell that turns a current version plus a bump type into a new one."""
    doc = yaml.safe_load(BUMP_ACTION.read_text())
    for step in doc["runs"]["steps"]:
        if step.get("id") == "bump":
            return step["run"]
    return None


def _bump(script: str, current: str, bump_type: str) -> tuple[int, str | None]:
    """Run the arithmetic for `current` + `bump_type`; return (exit code, new_version)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "out"
        out.write_text("")
        body = script.replace(
            "${{ steps.read.outputs.current }}", "$SIM_CURRENT"
        ).replace("${{ inputs.bump-type }}", "$SIM_TYPE")
        proc = subprocess.run(
            ["bash", "-e", "-c", body],
            env={
                **os.environ,
                "SIM_CURRENT": current,
                "SIM_TYPE": bump_type,
                "GITHUB_OUTPUT": str(out),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        new = next(
            (
                line.split("=", 1)[1]
                for line in out.read_text().splitlines()
                if line.startswith("new_version=")
            ),
            None,
        )
        return proc.returncode, new


def _release_resolve_script() -> str | None:
    """The verbatim shell that decides whether a release should happen."""
    doc = yaml.safe_load(ENTRYPOINT.read_text())
    for step in doc["jobs"]["resolve"]["steps"]:
        if step.get("id") == "resolve":
            return step["run"]
    return None


def _release_resolve(
    script: str, content: str | None, tags: list[str]
) -> tuple[int, str | None, str | None]:
    """Run the release gate over a synthetic repo. Returns (rc, version, should_release).

    Reads VERSION relative to cwd and shells out to `git describe`, so this needs
    a real repository rather than a bare file. Each tag gets its own commit so
    `git describe` resolves to exactly one answer instead of tie-breaking.
    """
    with tempfile.TemporaryDirectory() as tmp:
        repo = pathlib.Path(tmp) / "repo"
        repo.mkdir()
        out = pathlib.Path(tmp) / "out"
        out.write_text("")
        for cmd in (
            ["git", "init", "-q", "-b", "main", str(repo)],
            ["git", "-C", str(repo), "config", "user.email", "t@example.com"],
            ["git", "-C", str(repo), "config", "user.name", "T"],
        ):
            subprocess.run(cmd, check=True, capture_output=True)
        commit = ["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "c"]
        subprocess.run(commit, check=True, capture_output=True)
        for tag in tags:
            subprocess.run(commit, check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "tag", tag], check=True)
        if content is not None:
            (repo / "VERSION").write_text(content)
        proc = subprocess.run(
            ["bash", "-e", "-c", script],
            cwd=repo,
            env={**os.environ, "GITHUB_OUTPUT": str(out)},
            capture_output=True,
            text=True,
            check=False,
        )
        outputs = dict(
            line.split("=", 1) for line in out.read_text().splitlines() if "=" in line
        )
        return proc.returncode, outputs.get("version"), outputs.get("should_release")


def main() -> int:
    failures: list[str] = []
    checked = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal checked
        checked += 1
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

    # 6. The reader that resolves the base version must accept every shape
    #    bump-version's writers emit. Every check above is structural, which is
    #    why a keyed-only reader passed all of them and still failed at run time:
    #    bump-version writes a *bare* value for a file named VERSION, so nothing
    #    structural could see the disagreement. These execute the real block.
    update_steps = [
        s for s in yaml.safe_load(BUMP_ACTION.read_text())["runs"]["steps"] if s.get("id") == "update"
    ]
    check("bump-version has one update step", len(update_steps) == 1, f"found {len(update_steps)}")

    script = _reader_script()
    check("base-version reader step exists", script is not None)

    if update_steps and script:
        writer = update_steps[0]["run"]
        check(
            "bump-version's generic writer emits a bare value",
            "generic|manual)" in writer and 'echo "$NEW_VERSION" > "$FILE"' in writer,
            "writer shape changed; the reader contract must be re-derived",
        )

# Distinct from the forward-move guard, which only proves a bump moves forward:
# this proves `minor` produces the right number. Bumping PATCH instead still
# passes that guard, so a wrong version would ship with every check green.
        bump = _bump_script()
        check("bump arithmetic step exists", bump is not None)

        if bump:
            for current, kind, want, why in [
                ("0.15.0", "minor", "0.16.0",
                 "REGRESSION: feat/ + 0.15.0 must yield 0.16.0, the version #62 ships"),
                ("0.15.7", "minor", "0.16.0",
                 "REGRESSION: minor must zero the patch, not carry it"),
                ("0.15.0", "patch", "0.15.1", "patch moves only the patch"),
                ("0.15.9", "patch", "0.15.10", "patch rolls into a double digit"),
                ("0.15.0", "major", "1.0.0", "major zeroes minor and patch"),
                ("0.9.9", "minor", "0.10.0", "minor rolls into a double digit"),
            ]:
                code, got = _bump(bump, current, kind)
                check(
                    why,
                    code == 0 and got == want,
                    f"{current} --{kind}--> exit={code} got={got!r} want={want!r}",
                )

        code, resolved = _resolve(script, "0.15.0\n")
        check(
            "reader resolves the bare value the writer emits",
            code == 0 and resolved == "0.15.0",
            f"exit={code} resolved={resolved!r}",
        )

        code, resolved = _resolve(script, "name: galaxy\nversion: 1.7.2\n")
        check(
            "reader still resolves a keyed version (galaxy.yml)",
            code == 0 and resolved == "1.7.2",
            f"exit={code} resolved={resolved!r}",
        )

        code, resolved = _resolve(script, "version: 2.0.0\n0.9.9\n")
        check(
            "keyed form wins over a stray bare line",
            code == 0 and resolved == "2.0.0",
            f"exit={code} resolved={resolved!r}",
        )

        code, resolved = _resolve(script, "not-a-version\n")
        check(
            "reader still rejects a file with no version",
            code != 0 and resolved is None,
            f"exit={code} resolved={resolved!r}",
        )

# 7. Section 6's argument, applied to the release gate: a wrong comparison here
#    passes section 5's structural checks and then decides the opposite at run
#    time — skipping a release that should ship, or republishing a shipped one.
    rel = _release_resolve_script()
    check("release resolve step exists", rel is not None)

    if rel:
        # (VERSION contents, tags, rc, version, should_release, why)
        for content, tags, rc, ver, rel_out, why in [
            ("0.16.0\n", ["v0.15.0"], 0, "0.16.0", "true",
             "REGRESSION: a bumped VERSION past the latest tag must publish"),
            ("0.15.0\n", ["v0.15.0"], 0, "0.15.0", "false",
             "REGRESSION: an already-released VERSION must skip, not republish"),
            ("0.16.0\n", [], 0, "0.16.0", "true",
             "first release with no tags yet must publish"),
            ("0.15.0\n", ["v0.14.0", "v0.15.0"], 0, "0.15.0", "false",
             "the nearest reachable tag is the one that counts"),
            ("0.16.0\n\n", ["v0.15.0"], 0, "0.16.0", "true",
             "trailing blank lines must not break the read"),
            (None, ["v0.15.0"], 1, None, None,
             "a missing VERSION must fail loudly, never publish"),
            ("0.16.0-rc.1\n", ["v0.15.0"], 1, None, None,
             "a prerelease VERSION must be refused"),
            ("not-a-version\n", ["v0.15.0"], 1, None, None,
             "garbage VERSION must be refused"),
        ]:
            code, got_v, got_rel = _release_resolve(rel, content, tags)
            check(
                why,
                code == rc and got_v == ver and got_rel == rel_out,
                f"exit={code} version={got_v!r} should_release={got_rel!r}",
            )

    if failures:
        print(f"version authority FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        f"version authority OK ({checked} checks: contract, action, tag wiring, VERSION, "
        "entrypoint, version-file reader/writer round trip, release gate)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
