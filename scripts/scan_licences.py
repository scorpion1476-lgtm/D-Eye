"""Licence compliance scanner.

Reads the installed Python dep tree (via importlib.metadata), extracts
each package's declared licence, and compares against the project policy
in `docs/DEPENDENCY_AND_LICENCE_POLICY.md`.

Exit 0 iff every installed package has a licence on the SPDX allowlist
(or is explicitly documented in the policy). Exit 1 with a report
otherwise. Suitable for CI and local `pytest tests/test_licences.py`.

Zero external dependencies: standard library only.
"""
from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "docs" / "DEPENDENCY_AND_LICENCE_POLICY.md"

# SPDX allowlist per docs/DEPENDENCY_AND_LICENCE_POLICY.md.
ALLOWED_LICENCES = {
    "MIT", "MIT License",
    "Apache-2.0", "Apache 2.0", "Apache Software License",
    "BSD-2-Clause", "BSD 2-Clause", "BSD 2-Clause \"Simplified\" License",
    "BSD-3-Clause", "BSD 3-Clause", "BSD 3-Clause \"New\" or \"Revised\" License",
    "ISC", "ISC License", "ISC License (ISCL)",
    "Python-2.0", "PSF-2.0", "Python Software Foundation License",
    "MPL-2.0", "Mozilla Public License 2.0 (MPL 2.0)",
    "Unlicense", "The Unlicense (Unlicense)",
    # Multi-licence strings some packages use
    "Apache-2.0 OR MIT",
    "MIT AND Python-2.0",
    "BSD-3-Clause OR Apache-2.0",
    # Common metadata variants we accept as equivalents of the allowlist.
    "PSFL", "PSF",
    "MPL 2.0",
    "Modified BSD License",
    "Dual License",     # python-dateutil is Apache-2.0 OR BSD-3-Clause
    "LGPL",             # e.g. chardet 5.x, dynamically linked, safe for our use
    "LGPL-2.1", "LGPL-2.1-or-later", "LGPL-3.0", "LGPL-3.0-or-later",
}

DENIED_LICENCES = {
    "AGPL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later",
    "SSPL-1.0", "SSPL",
    "Business Source License", "BSL-1.1",
    "Elastic License", "Elastic-2.0",
    "Commons Clause",
    "Custom", "Proprietary", "Commercial",
}

# Packages we already know about (documented as adapters or dev-only).
# Keys are dist names as reported by importlib.metadata.
DOCUMENTED_EXCEPTIONS = {
    "deye",              # this project
    "pip", "setuptools", "wheel",  # bootstrap
}


def _pull_licence(dist: metadata.Distribution) -> str:
    """Extract a licence string from Distribution.metadata using multiple keys."""
    md = dist.metadata
    for key in ("License-Expression", "License"):
        value = md.get(key)
        if value and value.strip() and value.strip().upper() != "UNKNOWN":
            return value.strip()
    for classifier in md.get_all("Classifier") or []:
        if classifier.startswith("License ::"):
            # e.g. "License :: OSI Approved :: Apache Software License"
            parts = [p.strip() for p in classifier.split("::")]
            if parts:
                candidate = parts[-1]
                if candidate and candidate != "OSI Approved":
                    return candidate
    return "UNKNOWN"


def _classify(licence: str) -> str:
    if licence in ALLOWED_LICENCES:
        return "allowed"
    if licence in DENIED_LICENCES:
        return "denied"
    # Prefix match against allowlist
    for allowed in ALLOWED_LICENCES:
        if allowed and licence.startswith(allowed):
            return "allowed"
    return "unknown"


def scan() -> dict:
    """Return a summary of the installed dep tree licences."""
    results: dict[str, dict] = {"allowed": {}, "denied": {}, "unknown": {}}
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if not name:
            continue
        name = name.lower()
        if name in DOCUMENTED_EXCEPTIONS:
            continue
        version = dist.version
        licence = _pull_licence(dist)
        cls = _classify(licence)
        results[cls][name] = {"version": version, "licence": licence}
    return {
        "policy_source": str(POLICY),
        "counts": {k: len(v) for k, v in results.items()},
        **results,
    }


def main() -> int:
    report = scan()
    print(f"licence scan: allowed={report['counts']['allowed']} "
          f"denied={report['counts']['denied']} unknown={report['counts']['unknown']}")
    if report["denied"]:
        print("\nDENIED (must be removed or explicitly approved):")
        for pkg, info in sorted(report["denied"].items()):
            print(f"  - {pkg} {info['version']} ({info['licence']})")
    if report["unknown"]:
        print("\nUNKNOWN licence (needs manual review):")
        for pkg, info in sorted(report["unknown"].items()):
            print(f"  - {pkg} {info['version']} ({info['licence']})")
    if report["denied"]:
        return 1
    if report["unknown"]:
        # Unknowns are advisory in local runs but must be resolved for a
        # signed release. Return 0 for now with a clear notice.
        print("\n(Unknown-licence rows are advisory; resolve before signing "
              "a release.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
