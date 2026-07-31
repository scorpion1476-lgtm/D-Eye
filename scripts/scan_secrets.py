"""Deterministic secret scanner (C09-F005).

Scans text-like files under a directory for a curated set of live-
credential patterns, printing every hit as one line and returning a
non-zero exit code if anything is found. Uses only Python stdlib.

Patterns are the same set enforced by tests/test_no_secrets_in_repo.py
so a repo that passes that test always passes this script -- the
script exists as a reusable command-line surface for
pre-commit / CI / release checks.

Exit codes:
    0 - no matches
    1 - matches found (details on stdout)
    2 - path not readable
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_user_key",   re.compile(r"sk_user_[A-Za-z0-9]{16,}")),
    ("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9]{20,}")),
    ("aws_access_key_id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token",      re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("bearer_long",       re.compile(r"Bearer\s+[A-Za-z0-9]{20,}")),
]

SKIP_DIRS = {
    ".venv", "venv", ".git", "__pycache__", "build", "dist",
    "node_modules", ".ruff_cache", ".pytest_cache", ".mypy_cache", ".eggs",
}
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".toml", ".cfg", ".ini", ".json", ".yaml", ".yml",
    ".sh", ".env", ".example", ".gitignore", ".dockerfile", "",
}


def _iter_text_files(root: Path, *, include_tests: bool):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not include_tests and "/tests/" in str(p):
            continue
        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield p


def scan(root: Path, *, include_tests: bool = False) -> list[dict]:
    findings: list[dict] = []
    for path in _iter_text_files(root, include_tests=include_tests):
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for name, pat in PATTERNS:
            for m in pat.finditer(text):
                # Deterministic hit record: relative path, pattern name,
                # 1-based line number, and column so a diff of two runs
                # against identical inputs stays byte-identical.
                line = text[: m.start()].count("\n") + 1
                col = m.start() - text[: m.start()].rfind("\n")
                findings.append({
                    "path": str(path.relative_to(root)),
                    "pattern": name,
                    "line": line,
                    "col": col,
                })
    findings.sort(key=lambda f: (f["path"], f["line"], f["col"]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan a directory for live-credential patterns."
    )
    parser.add_argument("--path", default=".",
                        help="Directory to scan (default: cwd)")
    parser.add_argument("--include-tests", action="store_true",
                        help="Also scan under */tests/*")
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.is_dir():
        sys.stderr.write(f"scan_secrets: not a directory: {root}\n")
        return 2

    findings = scan(root, include_tests=args.include_tests)
    if not findings:
        sys.stdout.write("no secrets found\n")
        return 0
    for f in findings:
        sys.stdout.write(f"{f['path']}:{f['line']}:{f['col']}: {f['pattern']}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
