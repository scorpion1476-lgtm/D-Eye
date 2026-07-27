#!/usr/bin/env bash
# Package D-Eye into a clean, secret-free ZIP.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/mnt/user-data/outputs/D-Eye-0.1.0.zip}"
cd "$ROOT"
# Refuse to package if any live-token pattern is present outside tests.
if grep -rEq "sk_user_[A-Za-z0-9]{16,}" --include="*" . 2>/dev/null; then
  if grep -rE "sk_user_[A-Za-z0-9]{16,}" --include="*" . | grep -qv "tests/"; then
    echo "ABORT: secret-shaped string found outside tests"; exit 1
  fi
fi
find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
rm -f "$OUT"
zip -rq "$OUT" . -x '*.pyc' -x '*/__pycache__/*' -x '*.egg-info/*' -x '.git/*'
echo "packaged -> $OUT"
