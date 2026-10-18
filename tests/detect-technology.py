#!/usr/bin/env python3
"""Regression tests for technology detection.

These run the composite action's own bash script against synthetic repositories,
so the assertions describe what consumers actually observe rather than what the
script appears to intend.

Since P1 the repository's `mise.toml` is the authority for language/toolchain
detection: the declared tools are read through `mise ls --json`, and the file
sniffers for mise-managed languages (python, go, rust, java, nodejs) are gone.
A manifest alone (`go.mod`, `pyproject.toml`, `package.json`, ...) is
deliberately NOT a signal any more, which is why those fixtures now declare a
`mise.toml` and stub the `mise` binary.

The `primary` vocabulary is contractual: `workflows-lib` feeds it straight into
`run-tests`, which branches on ansible, python, nodejs, go, rust, java, docker
and generic. A change that silently drops a language from that set makes the
consumer run the wrong (or no) test command, which is why each case below pins
the exact value.

Exit code 0 when every case matches, 1 otherwise.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ACTION = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "actions"
    / "detect-technology"
    / "action.yml"
)

MISE_WARNING = "::warning::mise.toml not found — add one to declare the toolchain"
TOX_NO_FILE_WARNING = "no tox file found"
TOX_NO_ENVS_WARNING = "declares no py<version> envs"

# A galaxy.yml as produced by `ansible-galaxy collection init`: notably no
# `type:` field, which is why detection must key on the file's presence.
GALAXY_YML = (
    "namespace: testns\nname: testcol\nversion: 1.0.0\nreadme: README.md\n"
    "authors:\n  - Test\ndescription: Test collection\nlicense:\n  - MIT\n"
    "dependencies: {}\nrepository: https://example.com\nbuild_ignore: []\n"
)

MISE_TOML_PYTHON = '[tools]\npython = "3.12"\n'


def mise_json(*tools: str) -> str:
    """Payload in the exact shape `mise ls --json` emits.

    The real command lists every tool mise knows about - including tools that a
    config file requests but that are not installed - as an object keyed by tool
    name, each value carrying at least these fields. Replaying that shape keeps
    the action's parser honest about the real schema.
    """
    return json.dumps(
        {
            tool: {
                "version": "1.0.0",
                "requested_version": "1",
                "installed": True,
                "active": True,
            }
            for tool in tools
        },
        indent=2,
    )


# fixture name -> {
#   files:     files to create in the synthetic repo
#   mise:      optional `mise ls --json` payload exposed through a stub `mise`
#   env:       optional environment overrides for the action step
#   expect:    expected GITHUB_OUTPUT key -> value
#   warns:     optional override for the expected missing-mise.toml warning
#   warns_tox: optional expected tox warning substring; defaults to the
#              missing-file warning when python is declared without a tox file
# }
CASES: dict[str, dict] = {
    # --- mise-first: the declared toolchain is the authority -------------
    "mise-python": {
        "files": {"mise.toml": MISE_TOML_PYTHON},
        "mise": mise_json("python"),
        "expect": {
            "primary": "python",
            "python": "mise.toml",
            "mise": "mise.toml",
            "count": "1",
        },
    },
    # mise shortname `node` must land in the vocabulary as `nodejs`.
    "mise-node-maps-to-nodejs": {
        "files": {"mise.toml": '[tools]\nnode = "20"\n'},
        "mise": mise_json("node"),
        "expect": {"primary": "nodejs", "nodejs": "mise.toml", "count": "1"},
    },
    "mise-go": {
        "files": {"mise.toml": '[tools]\ngo = "1.22"\n'},
        "mise": mise_json("go"),
        "expect": {"primary": "go", "go": "mise.toml", "count": "1"},
    },
    "mise-rust": {
        "files": {"mise.toml": '[tools]\nrust = "stable"\n'},
        "mise": mise_json("rust"),
        "expect": {"primary": "rust", "rust": "mise.toml", "count": "1"},
    },
    "mise-java": {
        "files": {"mise.toml": '[tools]\njava = "21"\n'},
        "mise": mise_json("java"),
        "expect": {"primary": "java", "java": "mise.toml", "count": "1"},
    },
    # A mise-managed tool outside the vocabulary is reported but must never
    # become `primary` (run-tests has no branch for it).
    "mise-unsupported-tool-stays-generic": {
        "files": {"mise.toml": '[tools]\nterraform = "1.9"\n'},
        "mise": mise_json("terraform"),
        "expect": {"primary": "generic", "count": "1"},
    },
    # --- a manifest alone is no longer a signal --------------------------
    "go-mod-without-mise-is-generic": {
        "files": {"go.mod": ""},
        "expect": {"primary": "generic", "go": "", "count": "0"},
        "warns": True,
    },
    # Removing the python sniffer must not resurrect it from a stray stub.
    "python-manifest-without-mise-is-generic": {
        "files": {"pyproject.toml": ""},
        "expect": {"primary": "generic", "python": "", "count": "0"},
        "warns": True,
    },
    # The stub exists on PATH but there is no mise.toml: a runner's global mise
    # config must not leak a technology into this repo.
    "mise-ignored-without-manifest": {
        "files": {},
        "mise": mise_json("python"),
        "expect": {"primary": "generic", "python": "", "count": "0"},
        "warns": True,
    },
    # --- the missing-mise.toml warning -----------------------------------
    "missing-mise-warns": {
        "files": {"Makefile": ""},
        "expect": {"primary": "generic", "generic": "Makefile", "count": "1"},
        "warns": True,
    },
    "missing-mise-warning-can-be-suppressed": {
        "files": {"Makefile": ""},
        "env": {"WARN_ON_MISSING_MISE": "false"},
        "expect": {"primary": "generic", "generic": "Makefile", "count": "1"},
        "warns": False,
    },
    "mise-present-does-not-warn": {
        "files": {"mise.toml": MISE_TOML_PYTHON},
        "mise": mise_json("python"),
        "expect": {"primary": "python", "count": "1"},
        "warns": False,
    },
    # --- file-based technologies that are NOT mise-managed ---------------
    "ansible-collection": {
        "files": {"galaxy.yml": GALAXY_YML},
        "expect": {
            "primary": "ansible",
            "ansible-collection": "galaxy.yml",
            "count": "1",
        },
    },
    "docker-file": {
        "files": {"Dockerfile": ""},
        "expect": {"primary": "docker", "container": "Dockerfile", "count": "1"},
    },
    "docker-containerfile": {
        "files": {"Containerfile": ""},
        "expect": {"primary": "docker", "container": "Containerfile", "count": "1"},
    },
    "docker-compose": {
        "files": {"Dockerfile": "", "docker-compose.yml": ""},
        "expect": {"primary": "docker", "count": "1"},
    },
    # The Helm chart file is Chart.yaml; sniffing Chart.yml detected nothing.
    "helm-chart": {
        "files": {"Chart.yaml": ""},
        "expect": {"primary": "generic", "helm": "Chart.yaml", "count": "1"},
    },
    "generic-makefile": {
        "files": {"Makefile": ""},
        "expect": {"primary": "generic", "generic": "Makefile", "count": "1"},
    },
    "empty": {"files": {}, "expect": {"primary": "generic", "count": "0"}},
    "execution-environment": {
        "files": {"execution-environment.yml": ""},
        "expect": {
            "primary": "generic",
            "ansible-execution-environment": "execution-environment.yml",
            "count": "1",
        },
    },
    # --- precedence ------------------------------------------------------
    # ansible outranks every other signal, matching the precedence the consumer
    # previously relied on from its own local detector.
    "ansible-beats-python": {
        "files": {"galaxy.yml": GALAXY_YML, "mise.toml": MISE_TOML_PYTHON},
        "mise": mise_json("python"),
        "expect": {"primary": "ansible", "count": "2"},
    },
    "python-beats-nodejs": {
        "files": {"mise.toml": '[tools]\npython = "3.12"\nnode = "20"\n'},
        "mise": mise_json("python", "node"),
        "expect": {"primary": "python", "count": "2"},
    },
    # --- python-matrix ---------------------------------------------------
    "matrix-from-tox-env-list": {
        "files": {
            "mise.toml": MISE_TOML_PYTHON,
            "tox.ini": "[tox]\nenv_list = py310,py311,py312\n",
        },
        "mise": mise_json("python"),
        "expect": {
            "primary": "python",
            "python-matrix": '["3.10", "3.11", "3.12"]',
        },
    },
    "matrix-from-legacy-envlist": {
        "files": {
            "mise.toml": MISE_TOML_PYTHON,
            "tox.ini": "[tox]\nenvlist = py39,py310\n",
        },
        "mise": mise_json("python"),
        "expect": {"python-matrix": '["3.9", "3.10"]'},
    },
    "matrix-from-multiline-env-list": {
        "files": {
            "mise.toml": MISE_TOML_PYTHON,
            "tox.ini": "[tox]\nenv_list =\n    py310\n    py313\n\n[testenv]\ncommands = pytest\n",
        },
        "mise": mise_json("python"),
        "expect": {"python-matrix": '["3.10", "3.13"]'},
    },
    # tox-ansible.ini counts when the configured tox.ini is absent.
    "matrix-from-tox-ansible-ini": {
        "files": {
            "mise.toml": MISE_TOML_PYTHON,
            "tox-ansible.ini": "[tox]\nenv_list = py310\n",
        },
        "mise": mise_json("python"),
        "expect": {"python-matrix": '["3.10"]'},
    },
    # No tox file: single-version fallback plus a warning naming both candidates.
    "matrix-without-tox-file-falls-back": {
        "files": {"mise.toml": MISE_TOML_PYTHON},
        "mise": mise_json("python"),
        "expect": {"python-matrix": '["3.12"]'},
        "warns_tox": "no tox file found",
    },
    # A tox env list with no py<version> tokens cannot build a matrix either.
    "matrix-with-no-py-envs-falls-back": {
        "files": {
            "mise.toml": MISE_TOML_PYTHON,
            "tox.ini": "[tox]\nenv_list = lint\n",
        },
        "mise": mise_json("python"),
        "expect": {"python-matrix": '["3.12"]'},
        "warns_tox": "declares no py<version> envs",
    },
    # The fallback version is the action input, not a hardcoded value.
    "matrix-fallback-uses-python-version-input": {
        "files": {"mise.toml": MISE_TOML_PYTHON},
        "mise": mise_json("python"),
        "env": {"PYTHON_VERSION": "3.11"},
        "expect": {"python-matrix": '["3.11"]'},
    },
    # Non-python repos still get a one-element matrix so the unit job runs.
    "matrix-non-python-single-version": {
        "files": {"mise.toml": '[tools]\ngo = "1.22"\n'},
        "mise": mise_json("go"),
        "expect": {"python-matrix": '["3.12"]'},
    },
}


def load_step() -> tuple[str, dict[str, str]]:
    """Return the detection script plus the env the action declares for it.

    The action passes its inputs through `env:` rather than interpolating
    `${{ inputs.* }}` into the shell, so the suite reproduces the real defaults
    by resolving each `env:` value against the action's own `inputs:` block.
    """
    document = yaml.safe_load(ACTION.read_text())
    step = document["runs"]["steps"][0]
    inputs = document.get("inputs") or {}
    env: dict[str, str] = {}
    for key, raw in (step.get("env") or {}).items():
        match = re.fullmatch(r"\$\{\{\s*inputs\.([\w-]+)\s*\}\}", str(raw).strip())
        if match:
            env[key] = str(inputs.get(match.group(1), {}).get("default", ""))
        else:
            env[key] = str(raw)
    return step["run"], env


def run_against(
    script: str,
    files: dict[str, str],
    env: dict[str, str],
    mise_payload: str | None = None,
) -> tuple[dict[str, str], str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, content in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        out = root / ".out"
        out.write_text("")
        run_env = {"PATH": "/usr/bin:/bin", **env, "GITHUB_OUTPUT": str(out)}
        if mise_payload is not None:
            # Stub `mise`. The payload is the captured shape of a real
            # `mise ls --json`, so only the binary is faked, not the schema.
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            stub = bin_dir / "mise"
            stub.write_text(
                f"#!/bin/bash\ncat <<'MISE_JSON'\n{mise_payload}\nMISE_JSON\n"
            )
            stub.chmod(0o755)
            run_env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
        result = subprocess.run(
            ["bash", "-c", script],
            cwd=root,
            env=run_env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"script failed: {result.stderr.strip()}")
        parsed: dict[str, str] = {}
        for line in out.read_text().splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                parsed[key.strip()] = value.strip()
        return parsed, result.stdout, result.stderr


def main() -> int:
    script, step_env = load_step()
    failures: list[str] = []

    for name, case in CASES.items():
        files = case["files"]
        expected = case["expect"]
        expect_warning = case.get("warns", "mise.toml" not in files)
        env = {**step_env, **case.get("env", {})}
        try:
            actual, stdout, stderr = run_against(script, files, env, case.get("mise"))
        except Exception as exc:  # noqa: BLE001 - report, do not abort the suite
            failures.append(f"{name}: {exc}")
            continue
        for key, want in expected.items():
            got = actual.get(key, "")
            if got != want:
                failures.append(f"{name}: {key} expected {want!r}, got {got!r}")
        warned = MISE_WARNING in f"{stdout}{stderr}"
        if warned != expect_warning:
            failures.append(
                f"{name}: mise warning expected {expect_warning}, got {warned}"
            )
        python_declared = (
            any(expected.get(key) for key in ("python", "ansible-beats-python"))
            or "mise.toml" in files
            and "python" in str(files.get("mise.toml", ""))
        )
        tox_file = "tox.ini" in files or "tox-ansible.ini" in files
        expect_tox_warning = case.get(
            "warns_tox",
            "no tox file found" if python_declared and not tox_file else None,
        )
        combined = f"{stdout}{stderr}"
        if expect_tox_warning:
            if expect_tox_warning not in combined:
                failures.append(
                    f"{name}: tox warning {expect_tox_warning!r} missing from output"
                )
        elif TOX_NO_FILE_WARNING in combined or TOX_NO_ENVS_WARNING in combined:
            failures.append(f"{name}: unexpected tox warning in output")

    if failures:
        print(f"detection FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"detection OK ({len(CASES)} fixtures)")
    return 0


def test_main():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
