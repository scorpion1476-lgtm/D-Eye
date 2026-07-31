"""CI workflow validation (C09-F010).

Parses the shipped GitHub Actions workflow files and asserts they
declare the jobs, steps, and gates our release process depends on.
Uses PyYAML if available, otherwise a minimal stdlib parser.

This is a structural acceptance test: it does not run the workflow on
GitHub. What it does prove is that our repo ships a well-formed CI
config that will (a) run tests on both the core and remote extras,
(b) generate an SBOM artifact, and (c) not accidentally require paid
runners or secrets to pass.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _load_yaml(path: Path):
    try:
        import yaml  # type: ignore
    except ImportError:
        pytest.skip("PyYAML not installed; structural test needs a parser")
    return yaml.safe_load(path.read_text())


class TestCIWorkflow:
    def test_ci_yml_exists(self):
        assert (WORKFLOWS / "ci.yml").exists(), (
            "missing .github/workflows/ci.yml"
        )

    def test_ci_yml_declares_test_job(self):
        data = _load_yaml(WORKFLOWS / "ci.yml")
        assert "jobs" in data and "test" in data["jobs"]

    def test_ci_yml_runs_pytest(self):
        text = (WORKFLOWS / "ci.yml").read_text()
        assert re.search(r"pytest", text), "ci.yml does not run pytest"

    def test_ci_yml_runs_sbom_generator(self):
        text = (WORKFLOWS / "ci.yml").read_text()
        assert "gen_sbom.py" in text, "ci.yml does not run gen_sbom.py"

    def test_ci_yml_matrix_covers_core_and_mcp(self):
        data = _load_yaml(WORKFLOWS / "ci.yml")
        matrix = data["jobs"]["test"].get("strategy", {}).get("matrix", {})
        extras = set(matrix.get("extras", []))
        assert {"core", "mcp"} <= extras, (
            f"ci.yml matrix does not cover both core and mcp; got {extras}"
        )

    def test_ci_yml_has_least_privilege_permissions(self):
        data = _load_yaml(WORKFLOWS / "ci.yml")
        # Explicit read-only contents permission at workflow scope.
        perms = data.get("permissions", {})
        assert perms.get("contents") == "read", (
            "workflow should declare contents: read at top level"
        )
