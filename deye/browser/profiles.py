"""Browser profile management.

Handles named, isolated on-disk profile directories used by the
BrowserAdapter. Nothing here talks to the network or launches
Playwright; that lives in `deye/browser/__init__.py`. This module
just enumerates, creates, and removes profile directories on
disk with correct owner-only permissions.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from deye.browser import _profile_root

_NAME_OK = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


@dataclass
class ProfileInfo:
    name: str
    path: str
    size_bytes: int


def list_profiles() -> list[ProfileInfo]:
    root = _profile_root()
    if not root.exists():
        return []
    out: list[ProfileInfo] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        size = 0
        for f in child.rglob("*"):
            if f.is_file():
                size += f.stat().st_size
        out.append(ProfileInfo(name=child.name, path=str(child), size_bytes=size))
    return out


def create_profile(name: str) -> Path:
    if not _NAME_OK.match(name):
        raise ValueError(f"invalid profile name {name!r}")
    root = _profile_root()
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def remove_profile(name: str, *, confirm: bool = False) -> dict:
    if not _NAME_OK.match(name):
        raise ValueError(f"invalid profile name {name!r}")
    if not confirm:
        return {"ok": False, "reason": "confirm=True required (destructive)"}
    root = _profile_root()
    path = root / name
    if not path.exists():
        return {"ok": False, "reason": f"profile {name!r} does not exist"}
    shutil.rmtree(path)
    return {"ok": True, "removed": str(path)}


def profile_report() -> dict:
    root = _profile_root()
    profiles = list_profiles()
    return {
        "root": str(root),
        "count": len(profiles),
        "profiles": [asdict(p) for p in profiles],
        "boundary": "cookies live only in these dirs; never uploaded",
    }
