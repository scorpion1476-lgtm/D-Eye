"""Bulk-replace U+2013 EN DASH, U+2014 EM DASH, and U+2011 NON-BREAKING
HYPHEN with plain ASCII hyphen-minus (U+002D) across user-facing files.

Uses the same DEFAULT_UI_PATHS + ATTRIBUTION_EXCLUDES as
`scan_ui_dashes.py` so the fixer and scanner agree on scope. Writes
files in place. Reports files touched + total replacements.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scan_ui_dashes import (
    ATTRIBUTION_EXCLUDES,
    DEFAULT_UI_PATHS,
    _walk,
)

REPLACEMENTS = {
    "–": "-",  # en dash
    "—": "-",  # em dash
    "‑": "-",  # non-breaking hyphen
}


def fix_paths(paths: list[Path], dry_run: bool = False) -> dict:
    files_touched = 0
    total_replacements = 0
    detail: list[dict] = []
    for root in paths:
        for path in _walk(root):
            if path in ATTRIBUTION_EXCLUDES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            n_here = sum(text.count(ch) for ch in REPLACEMENTS)
            if n_here == 0:
                continue
            new_text = text
            for src, dst in REPLACEMENTS.items():
                new_text = new_text.replace(src, dst)
            if dry_run:
                detail.append({"path": str(path), "replacements": n_here})
            else:
                path.write_text(new_text, encoding="utf-8")
                detail.append({"path": str(path), "replacements": n_here})
            files_touched += 1
            total_replacements += n_here
    return {"files_touched": files_touched,
            "total_replacements": total_replacements,
            "detail": detail}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--paths", nargs="*")
    args = p.parse_args()
    paths = ([Path(p) for p in args.paths] if args.paths
             else [p for p in DEFAULT_UI_PATHS if p.exists()])
    result = fix_paths(paths, dry_run=args.dry_run)
    print(f"files touched: {result['files_touched']}")
    print(f"total replacements: {result['total_replacements']}")
    for d in result["detail"][:30]:
        print(f"  {d['path']}  {d['replacements']}")
    if len(result["detail"]) > 30:
        print(f"  ... {len(result['detail']) - 30} more files")
    return 0


if __name__ == "__main__":
    # Ensure scripts/ is on sys.path so `from scan_ui_dashes import ...` works
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
