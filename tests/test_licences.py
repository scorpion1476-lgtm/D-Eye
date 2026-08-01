"""Licence-drift compliance test.

Runs scripts/scan_licences.py against the currently installed dep tree.
Fails if any DENIED licence is present. Unknown licences are advisory
(they log to stdout but do not fail the test) so a new dep addition
does not silently ship — a reviewer must classify it.

Acceptance test for C11-F018 and C12-F021 (licence + attribution
tracking).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCAN = Path(__file__).resolve().parent.parent / "scripts" / "scan_licences.py"


def test_licence_scan_runs():
    assert SCAN.exists(), f"scan script missing at {SCAN}"


def test_no_denied_licences_in_installed_tree():
    r = subprocess.run(
        [sys.executable, str(SCAN)],
        capture_output=True, text=True, timeout=30,
    )
    # exit 0 = no denied. exit 1 = at least one denied. exit 2 = internal error.
    assert r.returncode != 2, f"scan crashed: {r.stderr}"
    if r.returncode == 1:
        raise AssertionError(
            "denied-licence dep in installed tree — see scan output:\n" + r.stdout
        )
    # exit 0: pass
    assert "denied=0" in r.stdout, f"unexpected scan output: {r.stdout[:400]}"
