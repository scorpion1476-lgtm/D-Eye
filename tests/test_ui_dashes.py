"""Regression: forbid U+2013 EN DASH, U+2014 EM DASH, U+2011 NON-BREAKING
HYPHEN anywhere in user-facing files.

Prints the exact file and line for every violation so CI output points
at the offender directly.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN = REPO_ROOT / "scripts" / "scan_ui_dashes.py"


@pytest.mark.skipif(not SCAN.exists(), reason="scanner script missing")
def test_no_forbidden_dashes_in_user_facing_files():
    r = subprocess.run(
        [sys.executable, str(SCAN)],
        capture_output=True, text=True, timeout=30,
    )
    # Exit 0 means clean; exit 1 means violations found (with details in stdout)
    assert r.returncode == 0, (
        "Forbidden Unicode long-dash characters found in user-facing files.\n"
        "Only ASCII hyphen-minus (U+002D) is allowed. Re-run\n"
        "  python3 scripts/fix_ui_dashes.py\n"
        "to bulk-replace. Scanner output:\n"
        f"{r.stdout}\n{r.stderr}"
    )


def test_scanner_actually_catches_a_planted_em_dash(tmp_path):
    """Meta-test: scanner is not silently broken."""
    bad = tmp_path / "bad.md"
    bad.write_text("This line has an em dash — which should fail.\n",
                   encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCAN), "--paths", str(bad)],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 1, "scanner failed to detect a planted em dash"
    assert "U+2014" in r.stdout or "EM DASH" in r.stdout


def test_scanner_actually_catches_a_planted_en_dash(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("This line has an en dash – which should fail.\n",
                   encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCAN), "--paths", str(bad)],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 1
    assert "U+2013" in r.stdout or "EN DASH" in r.stdout


def test_scanner_actually_catches_a_planted_nb_hyphen(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("This line has a nb hyphen ‑ which should fail.\n",
                   encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCAN), "--paths", str(bad)],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 1
    assert "U+2011" in r.stdout or "NON-BREAKING" in r.stdout


def test_scanner_passes_clean_ascii(tmp_path):
    good = tmp_path / "good.md"
    good.write_text("This line has only ASCII hyphens - like this - fine.\n",
                    encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCAN), "--paths", str(good)],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0
