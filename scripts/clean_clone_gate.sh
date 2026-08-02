#!/usr/bin/env bash
# Clean-clone gate: prove the repo installs and its full suite passes from a
# fresh public clone, following the README exactly. Installs the documented
# extras plus the optional FOSS browser extra (Playwright + Chromium) so the
# live headless browser acceptance tests actually run.
#
# Usage:
#   scripts/clean_clone_gate.sh [git-ref]
#
# Defaults to the feature branch. Clones the PUBLIC origin, so run it only
# after the ref has been pushed. Never pushes from the temp clone; deletes it
# on success. On failure the temp clone is left in place for inspection and
# its path is printed.
set -euo pipefail

REPO_URL="https://github.com/scorpion1476-lgtm/D-Eye.git"
REF="${1:-feature/production-complete-v1}"

WORK="$(mktemp -d)"
CLONE="${WORK}/D-Eye"
echo "clean-clone gate: ref=${REF}"
echo "clean-clone gate: workdir=${WORK}"

# Full clone (no --depth) so it matches the README's `git clone` exactly and
# history-dependent tests see the real repository history.
git clone --branch "${REF}" "${REPO_URL}" "${CLONE}"

cd "${CLONE}"
python3 -m venv .venv
./.venv/bin/python -m pip install --quiet --upgrade pip
# Documented extras for the full suite + the optional browser extra.
./.venv/bin/python -m pip install --quiet -e '.[dev,mcp,remote,browser]'
./.venv/bin/python -m playwright install chromium

echo "clean-clone gate: running full suite"
set +e
./.venv/bin/python -m pytest -q -rs
RC=$?
set -e

if [ "${RC}" -eq 0 ]; then
  echo "clean-clone gate: PASS (0 failures, 0 errors)"
  rm -rf "${WORK}"
  echo "clean-clone gate: temp clone removed"
else
  echo "clean-clone gate: FAIL rc=${RC}"
  echo "clean-clone gate: temp clone left at ${CLONE} for inspection"
fi
exit "${RC}"
