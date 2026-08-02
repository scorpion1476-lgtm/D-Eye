"""Live pip-audit against OSV.dev.

Real-network vulnerability scan. Skipped if osv.dev is unreachable
(no network / firewalled test host). Fails if any vulnerability is
reported against an installed dep.

Acceptance test for C11-F019 (rollback + version pinning + no vuln)
and C12-F034 (SBOM + CI security scanning).
"""
from __future__ import annotations

import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest


def _osv_reachable() -> bool:
    try:
        urllib.request.urlopen("https://osv.dev/", timeout=5)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _pip_audit_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("pip_audit") is not None


DUMP = Path(__file__).resolve().parent.parent / "scripts" / "dump_requirements.py"


@pytest.mark.skipif(not DUMP.exists(), reason="scripts/dump_requirements.py not found")
@pytest.mark.skipif(not _pip_audit_available(), reason="pip-audit not installed (dev extra)")
@pytest.mark.skipif(not _osv_reachable(), reason="osv.dev unreachable from this host")
def test_pip_audit_reports_no_vulnerabilities_against_osv(tmp_path):
    reqs = tmp_path / "reqs.txt"
    r = subprocess.run(
        [sys.executable, str(DUMP)],
        check=True, capture_output=True, text=True,
    )
    reqs.write_text(r.stdout)
    # The dump excludes deye and the venv bootstrap tooling, so a stdlib-only
    # core environment legitimately produces a short list. We only require that
    # the dumper ran and emitted valid `name==version` lines (or nothing at
    # all, which pip-audit treats as a clean, empty requirement set).
    for line in r.stdout.splitlines():
        line = line.strip()
        if line:
            assert "==" in line, f"malformed requirement line: {line!r}"

    audit = subprocess.run(
        [sys.executable, "-m", "pip_audit",
         "--disable-pip", "--no-deps",
         "-s", "osv",
         "-r", str(reqs),
         "-f", "columns"],
        check=False, capture_output=True, text=True, timeout=120,
    )
    combined = (audit.stdout or "") + "\n" + (audit.stderr or "")
    assert audit.returncode == 0, (
        f"pip-audit exit={audit.returncode}\n{combined}"
    )
    assert "No known vulnerabilities found" in combined, (
        f"pip-audit did not report clean:\n{combined}"
    )
