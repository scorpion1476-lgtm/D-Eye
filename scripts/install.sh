#!/usr/bin/env bash
# D-Eye one-step local installer for non-technical users (macOS / Linux).
# Installs D-Eye into a dedicated virtual environment, runs setup + a health
# check, and registers D-Eye with Claude Desktop and Claude Code. No sudo.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${DEYE_VENV:-$HOME/.deye/venv}"
# The extra to install ("mcp" ships the local MCP transport). Set to an empty
# string for a dependency-free core install. Overridable for automated checks.
EXTRA="${DEYE_INSTALL_EXTRA-mcp}"
# The interpreter to build the venv with. D-Eye needs Python >= 3.10; on macs
# whose default `python3` is the older system build, point this at a supported
# one (e.g. Homebrew's `python3.12`).
PYTHON="${DEYE_PYTHON:-python3}"

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  ver="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo unknown)"
  echo "error: D-Eye needs Python >= 3.10 but '$PYTHON' is $ver." >&2
  echo "       Install a newer Python and re-run, or set DEYE_PYTHON to it." >&2
  exit 1
fi

echo "==> Creating virtual environment at $VENV"
"$PYTHON" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> Installing D-Eye (with local MCP transport)"
pip install --upgrade pip >/dev/null
if [ -n "$EXTRA" ]; then
  pip install -e "$HERE[$EXTRA]"
else
  pip install -e "$HERE"
fi

echo "==> Preparing D-Eye (read-only, no secrets)"
deye setup
deye doctor || true

# Registering with Claude is a user-config side effect; DEYE_SKIP_CLAUDE=1 lets
# an automated install check exercise the venv + install + setup path without
# touching a real Claude Desktop / Claude Code configuration.
if [ "${DEYE_SKIP_CLAUDE:-0}" = "1" ] || [ "${DEYE_SKIP_CLAUDE:-}" = "true" ]; then
  echo "==> Skipping Claude registration (DEYE_SKIP_CLAUDE set)"
else
  echo "==> Registering with Claude Desktop and Claude Code"
  # Use the venv's python so Claude launches D-Eye from this environment.
  deye init-claude --python "$VENV/bin/python" --run-claude-code
fi

echo "==> Done. Restart Claude Desktop so it reloads MCP servers."
echo "    Verify anytime with:  $VENV/bin/deye doctor --surfaces"
