"""Emit a plain-format requirements list (pkg==version, one per line) for
the currently-installed non-editable, non-deye packages. pip-audit's
requirements parser rejects pip freeze's decorated output for editable
installs, so this script produces a clean input."""
from __future__ import annotations

import sys
from importlib import metadata

# The project itself plus the venv bootstrap tooling. These are not D-Eye
# dependencies (the core has none; pip/setuptools/wheel are supplied by the
# environment and upgraded independently), so they are excluded from the
# dependency vulnerability audit. This matches the DOCUMENTED_EXCEPTIONS in
# scripts/scan_licences.py, which excludes the same set.
_BOOTSTRAP = {"deye", "pip", "setuptools", "wheel"}


def main() -> int:
    lines: list[str] = []
    for dist in sorted(metadata.distributions(),
                       key=lambda d: (d.metadata["Name"] or "").lower()):
        name = dist.metadata["Name"]
        if not name or name.lower() in _BOOTSTRAP:
            continue
        version = dist.version
        lines.append(f"{name}=={version}")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
