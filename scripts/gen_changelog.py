"""Deterministic changelog generator (C09-F008).

Reads `git log` since the most recent tag (or the whole history when
there are no tags), buckets commit subjects by Conventional Commit
prefix (feat / fix / security / deps / perf / refactor / test / docs /
build / ci / chore), and emits a Markdown section per non-empty bucket.

Deterministic: given the same commit range and the same commit
subjects, the output is byte-identical.

Uses only the Python standard library and the system 'git' binary.
Exit codes:
    0 - Markdown printed to stdout
    2 - not a git repository, or git binary is unavailable
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

# Order matters: the header order in the output follows this list.
BUCKETS = OrderedDict((
    ("feat",     "Added"),
    ("fix",      "Fixed"),
    ("security", "Security"),
    ("perf",     "Performance"),
    ("refactor", "Refactored"),
    ("deps",     "Dependencies"),
    ("test",     "Tests"),
    ("docs",     "Documentation"),
    ("build",    "Build"),
    ("ci",       "CI"),
    ("chore",    "Chore"),
))
# subject line pattern: "<type>(<scope>)?: <message>"
_CC_RE = re.compile(r"^([a-z]+)(?:\([^)]*\))?!?:\s*(.+)$", re.IGNORECASE)


class GitError(RuntimeError):
    pass


def _git(args: list[str], cwd: Path) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=str(cwd),
            capture_output=True, text=True, check=False, timeout=15,
        )
    except FileNotFoundError as exc:
        raise GitError(f"git binary not available: {exc}") from exc
    if r.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed rc={r.returncode}: "
            f"{r.stderr.strip() or r.stdout.strip()}"
        )
    return r.stdout


def _range_since_last_tag(cwd: Path) -> str:
    """Return a git rev range expression for 'since the last tag'.
    Empty string means 'entire history'."""
    r = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"], cwd=str(cwd),
        capture_output=True, text=True, check=False, timeout=15,
    )
    if r.returncode == 0 and r.stdout.strip():
        return f"{r.stdout.strip()}..HEAD"
    return ""  # no tags: entire history


def _iter_subjects(cwd: Path, rev_range: str) -> list[tuple[str, str]]:
    args = ["log", "--no-merges", "--pretty=format:%h|%s"]
    if rev_range:
        args.append(rev_range)
    out = _git(args, cwd)
    subjects: list[tuple[str, str]] = []
    for line in out.splitlines():
        if "|" not in line:
            continue
        sha, subj = line.split("|", 1)
        subjects.append((sha.strip(), subj.strip()))
    return subjects


def _classify(subject: str) -> str:
    m = _CC_RE.match(subject)
    if not m:
        return "chore"
    prefix = m.group(1).lower()
    return prefix if prefix in BUCKETS else "chore"


def render(subjects: list[tuple[str, str]], *,
           title: str = "Changelog since last tag") -> str:
    grouped: dict[str, list[tuple[str, str]]] = {k: [] for k in BUCKETS}
    for sha, subj in subjects:
        grouped[_classify(subj)].append((sha, subj))

    lines: list[str] = [f"# {title}", ""]
    any_content = False
    for prefix, heading in BUCKETS.items():
        items = grouped[prefix]
        if not items:
            continue
        any_content = True
        lines.append(f"## {heading}")
        lines.append("")
        # Deterministic order: sort by subject then sha so identical inputs
        # produce identical outputs regardless of git log's own ordering.
        for sha, subj in sorted(items, key=lambda p: (p[1], p[0])):
            lines.append(f"- {subj} ({sha})")
        lines.append("")
    if not any_content:
        lines.append("_No commits in this range._")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Markdown changelog from git history."
    )
    parser.add_argument("--path", default=".",
                        help="Path to the working copy (default: cwd)")
    parser.add_argument("--range", default=None,
                        help="Explicit git rev range (default: since last tag)")
    parser.add_argument("--title", default="Changelog since last tag")
    args = parser.parse_args(argv)

    cwd = Path(args.path).resolve()
    try:
        rev = args.range if args.range is not None else _range_since_last_tag(cwd)
        subjects = _iter_subjects(cwd, rev)
    except GitError as exc:
        sys.stderr.write(f"gen_changelog: {exc}\n")
        return 2
    sys.stdout.write(render(subjects, title=args.title))
    return 0


if __name__ == "__main__":
    sys.exit(main())
