#!/usr/bin/env python3
"""Verify reusable workflows reach their own files via `$/`, never `./`.

The `$/path` self-repository reference resolves against the repository of the
file it appears in, at the running commit. A relative `./path` instead resolves
against whatever the caller checked out. Because these workflows are public
`workflow_call` contracts, a `./.github/...` reference inside one looks for the
target in the CALLER's workspace and dies with:

    Can't find 'action.yml' ... under '<caller>/.github/actions/<name>'

Regression to guard: `pr-check-and-bump.yml` and `pr-check-github-action.yml`
referenced their composite actions with `./`. workflows-lib's own PRs stayed
green (there `./` happens to resolve to this repo), but every consumer of the
floating `@v0` went red on the "Check PR" / lint jobs at once.

Only internal `./` references are rejected here. A pinned `$/...@ref` or a
cross-repo `{owner}/{repo}@ref` is a separate concern.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github/workflows"


def _iter_uses(node: Any) -> Iterator[str]:
    """Yield every `uses:` string found anywhere in a workflow document."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                yield value
            else:
                yield from _iter_uses(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_uses(item)


def check() -> list[str]:
    """Return `path: uses: <ref>` for every caller-relative internal reference."""
    offenders: list[str] = []
    paths = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    for path in paths:
        document = yaml.safe_load(path.read_text())
        for ref in _iter_uses(document):
            if ref.startswith("./.github/"):
                offenders.append(f"{path.relative_to(ROOT)}: uses: {ref}")
    return offenders


def main() -> int:
    offenders = check()
    if offenders:
        print("Internal references must use the `$/` self-repository prefix:\n")
        for line in offenders:
            print(f"  {line}")
        print(
            "\n`./` resolves against the caller's checkout, so consumers of a "
            "reusable workflow cannot resolve it. Use `$/.github/...`."
        )
        return 1
    print("local-action-refs OK: every internal reference uses `$/`")
    return 0


def test_no_caller_relative_internal_refs() -> None:
    assert check() == []


def test_main() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
