"""Repository verification utility (C09-F004).

Enumerates the current branch, HEAD SHA, remotes, and tags of a git
working copy, and emits a structured JSON report. Refuses OK when the
active branch is 'main' or 'master' unless --allow-main is passed --
this makes it safe to wire into a pre-release check that must never
succeed on the default branch.

Uses only the Python standard library and the system 'git' binary.
Exit codes:
    0 - report emitted; branch is not main/master, or --allow-main
    1 - report emitted; branch IS main/master and --allow-main was not passed
    2 - not a git repository, or git binary is unavailable
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


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
    return r.stdout.strip()


def collect(cwd: Path) -> dict:
    """Return a structured report for the repo at *cwd*."""
    # 'git rev-parse --show-toplevel' proves we are inside a repo AND gives
    # the canonical root path.
    top = _git(["rev-parse", "--show-toplevel"], cwd)
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    head = _git(["rev-parse", "HEAD"], cwd)
    remotes_raw = _git(["remote", "-v"], cwd)
    remotes: dict[str, dict[str, str]] = {}
    for line in remotes_raw.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        name, url, direction = parts[0], parts[1], parts[2].strip("()")
        remotes.setdefault(name, {})[direction] = url
    tags = [t for t in _git(["tag", "--list"], cwd).splitlines() if t.strip()]
    branches = [b.strip().lstrip("* ").strip()
                for b in _git(["branch", "--list"], cwd).splitlines()
                if b.strip()]
    return {
        "toplevel": top,
        "branch": branch,
        "head": head,
        "remotes": remotes,
        "tags": sorted(tags),
        "branches": sorted(branches),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a git repository.")
    parser.add_argument("--path", default=".",
                        help="Path to the working copy (default: cwd)")
    parser.add_argument("--allow-main", action="store_true",
                        help="Do not fail if branch is main/master")
    args = parser.parse_args(argv)

    cwd = Path(args.path).resolve()
    try:
        report = collect(cwd)
    except GitError as exc:
        sys.stderr.write(f"verify_repo: {exc}\n")
        sys.stdout.write(json.dumps({"error": str(exc)}, indent=2) + "\n")
        return 2

    on_main = report["branch"] in ("main", "master")
    report["on_default_branch"] = on_main
    report["allow_main"] = bool(args.allow_main)

    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    if on_main and not args.allow_main:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
