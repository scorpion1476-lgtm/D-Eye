"""Real update + rollback mechanism acceptance (C12-F035).

`lifecycle.apply_update(spec, python=...)` installs a pinned artifact into a
target interpreter, and `lifecycle.rollback_to(version)` is a thin wrapper that
pins `deye==<version>` through the same path. This test exercises the real
mechanism end-to-end and offline:

  - build two minimal wheels of a probe package (v1 and v2) with the stdlib;
  - create a fresh venv;
  - apply_update(v1) -> the venv reports version 1.0.0;
  - apply_update(v2) -> the venv reports version 2.0.0 (a real update);
  - apply_update(v1) -> the venv reports version 1.0.0 again (a real rollback).

No network: local wheels have no dependencies, so pip installs them directly.
This proves the install/rollback engine actually changes the installed version,
not just that it constructs a command string.
"""
from __future__ import annotations

import base64
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from deye import lifecycle

DIST = "deye-update-probe"
PKG = "deye_update_probe"


def _record_line(arcname: str, data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{arcname},sha256={digest},{len(data)}"


def _build_wheel(dest_dir: Path, version: str) -> Path:
    """Write a minimal, valid pure-python wheel and return its path."""
    distinfo = f"{PKG}-{version}.dist-info"
    files = {
        f"{PKG}/__init__.py": f'__version__ = "{version}"\n'.encode(),
        f"{distinfo}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {DIST}\n"
            f"Version: {version}\n"
        ).encode(),
        f"{distinfo}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: deye-test\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode(),
    }
    record = "\n".join(_record_line(name, data) for name, data in files.items())
    record += f"\n{distinfo}/RECORD,,\n"
    files[f"{distinfo}/RECORD"] = record.encode()

    wheel_path = dest_dir / f"{PKG}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return wheel_path


def _installed_version(python: Path) -> str | None:
    r = subprocess.run(
        [str(python), "-c",
         f"import importlib.metadata as m; print(m.version('{DIST}'))"],
        capture_output=True, text=True, timeout=60,
    )
    return r.stdout.strip() if r.returncode == 0 else None


def test_apply_update_and_rollback_change_the_installed_version(tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    w1 = _build_wheel(wheels, "1.0.0")
    w2 = _build_wheel(wheels, "2.0.0")

    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, timeout=120)
    py = venv / "bin" / "python"
    if not py.exists():  # Windows layout
        py = venv / "Scripts" / "python.exe"
    assert py.exists(), "venv python not created"

    # Install v1.
    res = lifecycle.apply_update(str(w1), python=str(py))
    assert res.get("ok"), f"apply_update(v1) failed: {res}"
    assert _installed_version(py) == "1.0.0"

    # Update to v2.
    res = lifecycle.apply_update(str(w2), python=str(py))
    assert res.get("ok"), f"apply_update(v2) failed: {res}"
    assert res.get("previous_version")  # engine records the prior version
    assert _installed_version(py) == "2.0.0"

    # Roll back to v1 (same engine, pinned spec).
    res = lifecycle.apply_update(str(w1), python=str(py))
    assert res.get("ok"), f"rollback to v1 failed: {res}"
    assert _installed_version(py) == "1.0.0"


def test_check_update_is_offline_safe_and_apply_update_dry_run_is_pinned():
    report = lifecycle.check_update(offline=True)
    d = report.to_dict()
    assert d["current_version"]
    assert "offline" in d["reason"].lower()

    dry = lifecycle.apply_update("deye==0.2.0", dry_run=True)
    assert dry["dry_run"] is True
    assert dry["would_run"][-1] == "deye==0.2.0"  # exact pinned spec, nothing run

    # rollback_to routes a pinned spec through the same engine.
    rolled = lifecycle.rollback_to("0.2.0", offline=True)
    assert rolled["ok"] is False and "offline" in rolled["reason"].lower()
