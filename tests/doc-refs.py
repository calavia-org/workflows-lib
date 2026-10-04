#!/usr/bin/env python3
"""Assert every documented workflows-lib consumer reference actually resolves.

The docs are the migration surface: a consumer copy-pastes a `uses:` line from
README.md or docs/*.md, and GitHub resolves the @ref at that moment. A ref that
names a tag nobody published fails only in the consumer's workflow run, days
later, far from the commit that introduced it -- and `actionlint` cannot see it,
because the reference lives in prose rather than in a workflow.

That is not hypothetical. This repository documented
`pr-check-and-bump.yml@v1` and `@v1.0.0` in four copy-pasteable examples while
publishing only the `v0` line, so every consumer following the documented path
resolved a nonexistent ref.

Two properties are asserted per reference, because a `uses:` line needs both: the
ref must be a published tag, and the path must exist *at that ref*. The second
check is deliberately not a working-tree check. A path that exists only in the
branch being merged, and in no published tag, passes a working-tree check while
still 404ing in a consumer's run -- and that is precisely the state this
repository is in between landing the consolidated actions and publishing the tag
that carries them. Resolving `<ref>:<path>` asks git the question a consumer's
workflow run actually asks.

The consequence is intentional: this test forbids documenting a ref that has not
been released yet. That is a feature. Forward references are exactly how the
`@v1`/`@v1.0.0` examples survived review in the first place, so a migration guide
must be written after the release that publishes its targets, not before.

A fenced block carrying a `doc-ref-test: skip` comment on its opening prose line is
exempt; that marker exists for before/after illustrations of the major-bump
convention, which deliberately name versions that do not exist yet.

Exit code 0 when every reference resolves, 1 otherwise.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = "calavia-org/workflows-lib"
DOCS = ("README.md", "RELEASE.md", "docs/release-artifacts.md", "docs/pr-check-and-bump.md")

# A documented reference: `<repo>/<path>@<ref>`, in any form documentation takes.
# The `uses:` prefix is deliberately not required -- requiring it would exempt every
# prose and markdown-table reference, which is how a migration guide is written and
# where a stale ref would hide while still 404ing for a consumer.
# Backtick, comma, semicolon and colon are excluded because git forbids them in a
# refname, so in a document they can only be markdown punctuation. A trailing `.` is
# legal inside a ref (`v0.15.0`) but illegal at the end of one, so it is stripped
# after capture -- adding it to this class instead would reject every version tag.
REF_RE = re.compile(
    re.escape(REPO) + r"/(?P<path>[^\s@`+,;:]+)@(?P<ref>[^\s`+,;:]+)"
)
FENCE_RE = re.compile(r"^\s*```")
SKIP_MARKER = "doc-ref-test: skip"


def doc_files() -> list[pathlib.Path]:
    """Every markdown file that can carry a copy-pasteable reference."""
    missing = [name for name in DOCS if not (ROOT / name).is_file()]
    if missing:
        print(f"error: expected documentation missing: {', '.join(missing)}")
        sys.exit(1)
    return [ROOT / name for name in DOCS]


def local_tags() -> set[str]:
    """Tags available in this clone.

    Requires a full clone. actions/checkout defaults to fetch-depth 1, which
    fetches only the tags pointing at the checked-out commit -- enough to make
    every published version look nonexistent, so the caller must deepen the
    clone rather than let this test invent failures.
    """
    proc = subprocess.run(
        ["git", "tag", "--list"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    tags = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    if not tags:
        print("error: no tags in this clone; run `git fetch --tags` (CI needs fetch-depth: 0)")
        sys.exit(1)
    return tags


def path_exists_at_ref(ref: str, path: str) -> bool:
    """Whether `path` is present in the tree that `ref` names.

    A working-tree check is not enough. A path added on the current branch and
    absent from every published tag passes `Path.exists()` while still failing in
    a consumer's run, because GitHub resolves `@ref` first and only then looks
    for the path inside it. `git cat-file -e <ref>:<path>` asks whether that
    resolution succeeds.

    Branches work as well as tags, so this stays meaningful if a doc ever pins a
    moving ref.
    """
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}:{path}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def checkable_lines(text: str) -> list[tuple[int, str]]:
    """Lines eligible for checking, as (line number, line).

    Drops the body of a fenced block whose immediately preceding non-blank line
    carries the skip marker. Everything else inside a fence is still checked --
    documentation examples are exactly the lines that must not rot.
    """
    kept: list[tuple[int, str]] = []
    in_fence = False
    exempt = False
    preceding = ""

    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            if in_fence:
                in_fence = False
                exempt = False
            else:
                in_fence = True
                exempt = SKIP_MARKER in preceding
            continue
        if in_fence and exempt:
            continue
        kept.append((number, line))
        if line.strip() and not in_fence:
            preceding = line.strip()

    return kept


def main() -> int:
    tags = local_tags()
    failures: list[str] = []
    checked = 0
    exempted = 0

    for doc in doc_files():
        relative = doc.relative_to(ROOT)
        text = doc.read_text(encoding="utf-8")

        checkable = checkable_lines(text)
        raw_hits = sum(len(REF_RE.findall(line)) for line in text.splitlines())
        exempted += raw_hits - sum(len(REF_RE.findall(line)) for _, line in checkable)

        for number, line in checkable:
            for match in REF_RE.finditer(line):
                path = match.group("path")
                ref = match.group("ref").rstrip(".")

                # `actions/NAME@v0` is the documented path *template*, not a real
                # action; its prose explains the shape without naming an action.
                if "NAME" in path:
                    continue

                checked += 1

                if ref not in tags:
                    failures.append(f"{relative}:{number}: @{ref} matches no published tag")
                elif not path_exists_at_ref(ref, path):
                    failures.append(
                        f"{relative}:{number}: {path} does not exist at @{ref}"
                    )

    for failure in failures:
        print(f"error: {failure}")

    print(f"checked {checked} documented consumer reference(s) against {len(tags)} published tag(s)")
    if exempted:
        print(f"skipped {exempted} reference(s) in explicitly marked illustration block(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())