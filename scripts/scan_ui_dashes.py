"""Scanner for forbidden long-dash Unicode characters in user-facing files.

Fails (exit 1) if it finds any of:
  U+2013 EN DASH
  U+2014 EM DASH
  U+2011 NON-BREAKING HYPHEN

Only ASCII hyphen-minus (U+002D) is allowed in user-facing text.

Attribution files (NOTICE, THIRD_PARTY_NOTICES.md, docs/FORENSIC_AUDIT_REPORT.md,
LICENSES/*) are excluded from the scan when they need to preserve legally
required wording. Every exclusion is listed explicitly at the top.

Usage:
    python3 scripts/scan_ui_dashes.py [--paths P1 P2 ...] [--report FILE]

Exit code:
    0 - clean
    1 - violations found (details printed and optionally written to --report)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent  # repository/deye
WORKSPACE = REPO_ROOT.parent.parent                 # workspace root

DEFAULT_UI_PATHS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "CHANGELOG.md",
    REPO_ROOT / "docs",
    REPO_ROOT / "plugin",
    REPO_ROOT / "deye",              # CLI help, error messages, log lines
    REPO_ROOT / "SECURITY.md",
    WORKSPACE / "docs",
    WORKSPACE / "reports",
]

# Attribution files (legally-required wording may include long dashes as
# part of the original text). These are excluded from UI-copy scanning
# but scanned separately for informational counts.
ATTRIBUTION_EXCLUDES = {
    REPO_ROOT / "NOTICE",
    REPO_ROOT / "THIRD_PARTY_NOTICES.md",
    REPO_ROOT / "LICENSE",
    REPO_ROOT / "docs" / "FORENSIC_AUDIT_REPORT.md",
    REPO_ROOT / "docs" / "LICENSE_INVENTORY.md",
}

# Skippable file suffixes (binary or generated).
_BINARY_SUFFIXES = {".pyc", ".png", ".jpg", ".gif", ".pdf", ".zip", ".gz",
                    ".tar", ".whl", ".ico", ".sqlite", ".db", ".pyo"}

FORBIDDEN = {
    0x2013: "U+2013 EN DASH",
    0x2014: "U+2014 EM DASH",
    0x2011: "U+2011 NON-BREAKING HYPHEN",
}


def _walk(root: Path):
    if root.is_file():
        yield root
        return
    if not root.exists():
        return
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in _BINARY_SUFFIXES:
            continue
        # skip caches
        parts = set(p.parts)
        if any(part in {"__pycache__", ".pytest_cache", ".ruff_cache",
                        ".venv", ".git", "node_modules", ".claude"}
               for part in parts):
            continue
        yield p


def scan_paths(paths: list[Path]) -> list[dict]:
    hits: list[dict] = []
    for root in paths:
        for path in _walk(root):
            if path in ATTRIBUTION_EXCLUDES:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            for line_num, line in enumerate(text.splitlines(), 1):
                for ch in line:
                    cp = ord(ch)
                    if cp in FORBIDDEN:
                        hits.append({
                            "path": str(path),
                            "line": line_num,
                            "char": FORBIDDEN[cp],
                            "codepoint": f"U+{cp:04X}",
                            "context": line.strip()[:120],
                        })
                        break  # one hit per line is enough for reporting
    return hits


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--paths", nargs="*",
                   help="Paths to scan (default: canonical UI paths)")
    p.add_argument("--report", help="Write JSON report to this path")
    p.add_argument("--include-attribution", action="store_true",
                   help="Also scan attribution files (for informational counts)")
    args = p.parse_args()

    if args.include_attribution:
        # temporarily empty the excludes
        ATTRIBUTION_EXCLUDES.clear()

    paths = ([Path(p) for p in args.paths] if args.paths
             else [p for p in DEFAULT_UI_PATHS if p.exists()])
    hits = scan_paths(paths)

    print(f"scanned {len(paths)} root path(s); {len(hits)} violation(s)")
    for h in hits[:50]:
        print(f"  {h['path']}:{h['line']}  {h['char']}  {h['context']}")
    if len(hits) > 50:
        print(f"  ... {len(hits) - 50} more")

    if args.report:
        Path(args.report).write_text(json.dumps({
            "scanned_paths": [str(p) for p in paths],
            "excluded_attribution": [str(p) for p in ATTRIBUTION_EXCLUDES],
            "violations": hits,
            "count": len(hits),
        }, indent=2))

    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
