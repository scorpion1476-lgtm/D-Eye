#!/usr/bin/env bash
# D-Eye SessionStart hook: LOCAL health check only.
# Deliberately does NOT: contact any remote service, download skills, or send
# telemetry. (Contrast with the reference plugin, which did all three.)
set -euo pipefail
if command -v deye >/dev/null 2>&1; then
  deye doctor 2>/dev/null || true
else
  echo "D-Eye not installed on PATH; run: pip install -e . && deye setup" >&2
fi
