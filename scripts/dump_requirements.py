"""Emit a plain-format requirements list (pkg==version, one per line) for
the currently-installed non-editable, non-deye packages. pip-audit's
requirements parser rejects pip freeze's decorated output for editable
installs, so this script produces a clean input."""
from __future__ import annotations

import sys
from importlib import metadata


def main() -> int:
    lines: list[str] = []
    for dist in sorted(metadata.distributions(),
                       key=lambda d: (d.metadata["Name"] or "").lower()):
        name = dist.metadata["Name"]
        if not name or name.lower() == "deye":
            continue
        version = dist.version
        lines.append(f"{name}=={version}")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
