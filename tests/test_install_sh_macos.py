"""Real end-to-end acceptance for the one-step local installer (C12-F022).

`scripts/install.sh` is the "true automatic installation on the user's Mac"
path. This test runs the actual installer, unmodified, in an isolated
environment and proves it produces a working `deye` command:

  - a fresh virtual environment is created at DEYE_VENV;
  - the package is installed into it (editable, from this checkout);
  - `deye setup` and `deye doctor` run against an isolated DEYE_HOME;
  - the resulting `deye` reports its version and a connector health summary.

DEYE_SKIP_CLAUDE=1 keeps the installer from touching a real Claude Desktop /
Claude Code configuration, so the test has no side effects outside tmp_path.

Installing the package needs the build backend from PyPI, so the test skips
cleanly when PyPI is unreachable (offline / firewalled host). It runs in the
clean-clone gate, which has network.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO / "scripts" / "install.sh"


def _pypi_reachable() -> bool:
    try:
        urllib.request.urlopen("https://pypi.org/simple/", timeout=5)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


pytestmark = [
    pytest.mark.skipif(sys.platform.startswith("win"),
                       reason="install.sh targets macOS / Linux"),
    pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available"),
    pytest.mark.skipif(not INSTALL_SH.exists(), reason="scripts/install.sh missing"),
]


@pytest.mark.skipif(not _pypi_reachable(), reason="PyPI unreachable; install needs the build backend")
def test_install_sh_produces_a_working_deye(tmp_path):
    venv = tmp_path / "venv"
    home = tmp_path / "home"
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(tmp_path),
        "DEYE_VENV": str(venv),
        "DEYE_HOME": str(home),
        "DEYE_SKIP_CLAUDE": "1",
        # Build the venv with a supported interpreter (the one running the
        # suite); a mac's default system python3 may predate the 3.10 floor.
        "DEYE_PYTHON": sys.executable,
        # Dependency-free core install: fastest faithful path; the shipped
        # default adds the [mcp] extra, exercised elsewhere.
        "DEYE_INSTALL_EXTRA": "",
    }

    proc = subprocess.run(
        ["bash", str(INSTALL_SH)],
        capture_output=True, text=True, env=env, timeout=600,
    )
    assert proc.returncode == 0, f"installer failed:\nSTDOUT{proc.stdout}\nSTDERR{proc.stderr}"

    deye_bin = venv / "bin" / "deye"
    assert deye_bin.exists(), f"installer did not produce {deye_bin}"

    # The produced command reports its version.
    ver = subprocess.run([str(deye_bin), "--version"],
                         capture_output=True, text=True, timeout=60)
    assert ver.returncode == 0, ver.stderr
    assert "deye" in ver.stdout.lower()

    # `deye doctor` runs the real health check against the isolated home and
    # emits its "N/M connectors usable" summary.
    doc = subprocess.run([str(deye_bin), "doctor"],
                         capture_output=True, text=True, timeout=120,
                         env={"PATH": env["PATH"], "HOME": str(tmp_path),
                              "DEYE_HOME": str(home)})
    assert doc.returncode == 0, doc.stderr
    assert "connectors usable" in doc.stdout

    # `deye setup` populated the isolated DEYE_HOME (no leakage to the real one).
    assert home.exists(), "DEYE_HOME was not created by `deye setup`"
