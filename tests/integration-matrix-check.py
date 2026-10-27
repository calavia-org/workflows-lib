#!/usr/bin/env python3
"""Fast integration smoke test that validates the CI matrix dimensions.

The reusable CI workflow is expected to fan out by python-version and
ansible-core when integration-matrix inputs are provided. This script simply
asserts that the matrix values it receives are from the expected sets, giving
us a cheap way to verify the Cartesian-product logic in workflows-lib itself.
"""

import os

EXPECTED_PYTHON = {"3.11", "3.12"}
EXPECTED_ANSIBLE = {"2.20", "milestone"}


def main() -> int:
    python_version = os.environ.get("MATRIX_PYTHON_VERSION", "")
    ansible_core = os.environ.get("MATRIX_ANSIBLE_CORE", "")
    scenario = os.environ.get("MATRIX_SCENARIO", "")

    if python_version not in EXPECTED_PYTHON:
        print(f"Unexpected MATRIX_PYTHON_VERSION: {python_version!r}")
        return 1

    if ansible_core not in EXPECTED_ANSIBLE:
        print(f"Unexpected MATRIX_ANSIBLE_CORE: {ansible_core!r}")
        return 1

    if scenario != "":
        print(f"Unexpected MATRIX_SCENARIO in non-ansible repo: {scenario!r}")
        return 1

    print(f"Matrix OK: python={python_version}, ansible-core={ansible_core}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
