#!/usr/bin/env python3
"""Generate a minimal CycloneDX-style SBOM for D-Eye (stdlib-only).

Records the D-Eye component plus its *declared* optional dependencies from
pyproject.toml, and any currently-installed runtime distributions. Intentionally
dependency-free so it runs anywhere Python does, including CI.

Usage: python scripts/gen_sbom.py [output.json]
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else "0.0.0"


def _declared_optional_deps() -> list[str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"\[project\.optional-dependencies\](.*?)(\n\[|\Z)", text, re.DOTALL)
    names: set[str] = set()
    if block:
        for raw in re.findall(r'"([^"]+)"', block.group(1)):
            name = re.split(r"[<>=!\[ ]", raw, maxsplit=1)[0]
            if name:
                names.add(name)
    return sorted(names)


def _installed_components() -> list[dict]:
    out = []
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if not name:
            continue
        out.append({
            "type": "library",
            "name": name,
            "version": dist.version,
            "purl": f"pkg:pypi/{name.lower()}@{dist.version}",
        })
    return sorted(out, key=lambda c: c["name"].lower())


def _declared_components() -> list[dict]:
    """D-Eye's real dependency posture: no core deps; optional extras listed."""
    out = []
    for name in _declared_optional_deps():
        out.append({
            "type": "library",
            "name": name,
            "scope": "optional",
            "purl": f"pkg:pypi/{name.lower()}",
        })
    return out


def build_sbom(*, installed: bool = False) -> dict:
    components = _installed_components() if installed else _declared_components()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [{"name": "deye-gen-sbom", "version": "1.0"}],
            "component": {
                "type": "application",
                "name": "deye",
                "version": _version(),
                "licenses": [{"license": {"id": "MIT"}}],
                "purl": f"pkg:pypi/deye@{_version()}",
            },
        },
        "components": components,
        "properties": [
            {"name": "deye:core-runtime-deps", "value": "none (standard library only)"},
            {"name": "deye:declared-optional-deps", "value": ", ".join(_declared_optional_deps())},
            {"name": "deye:sbom-scope",
             "value": "installed-environment" if installed else "declared-dependencies"},
        ],
    }


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--installed"]
    installed = "--installed" in argv
    out_path = Path(args[0]) if args else (ROOT / "sbom.json")
    out_path.write_text(json.dumps(build_sbom(installed=installed), indent=2), encoding="utf-8")
    print(f"wrote SBOM ({'installed' if installed else 'declared'}) -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
