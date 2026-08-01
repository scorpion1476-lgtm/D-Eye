#!/bin/sh
# Live dependency vulnerability audit against OSV.dev.
#
# Runs pip-audit in a mode that works with the D-Eye editable install:
# dumps the currently-installed non-editable deps to a temp file
# (via scripts/dump_requirements.py), then audits with --disable-pip
# and --no-deps against OSV.
#
# Exits 0 iff 'No known vulnerabilities found'. Exits non-zero otherwise,
# including on network failure.

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
REQS="${TMPDIR:-/tmp}/deye-audit-reqs-$$.txt"

trap 'rm -f "$REQS"' EXIT

"$PY" "$(dirname "$0")/dump_requirements.py" > "$REQS"
echo "==> auditing $(wc -l < "$REQS" | tr -d ' ') dependencies against OSV.dev"
"$PY" -m pip_audit --disable-pip --no-deps -s osv -r "$REQS" -f columns
