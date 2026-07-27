#!/usr/bin/env bash
# D-Eye one-step local installer for non-technical users (macOS / Linux).
# Installs D-Eye into a dedicated virtual environment, runs setup + a health
# check, and registers D-Eye with Claude Desktop and Claude Code. No sudo.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${DEYE_VENV:-$HOME/.deye/venv}"

echo "==> Creating virtual environment at $VENV"
python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> Installing D-Eye (with local MCP transport)"
pip install --upgrade pip >/dev/null
pip install -e "$HERE[mcp]"

echo "==> Preparing D-Eye (read-only, no secrets)"
deye setup
deye doctor || true

echo "==> Registering with Claude Desktop and Claude Code"
# Use the venv's python so Claude launches D-Eye from this environment.
deye init-claude --python "$VENV/bin/python" --run-claude-code

echo "==> Done. Restart Claude Desktop so it reloads MCP servers."
echo "    Verify anytime with:  $VENV/bin/deye doctor --surfaces"
