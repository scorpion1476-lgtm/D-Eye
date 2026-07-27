"""Automated local activation: register D-Eye with Claude Desktop and Claude Code.

`deye init-claude` merges a `deye` MCP server entry into the Claude Desktop
config for the current operating system (backing up any existing file first and
never clobbering other servers), and prints -- or, with ``--run-claude-code``,
runs -- the equivalent Claude Code command. It makes no network calls and needs
no elevated privileges.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def claude_desktop_config_path() -> Path:
    """Return the Claude Desktop config path for this OS (not guaranteed to exist)."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if os.name == "nt":
        base = os.environ.get("APPDATA", str(home / "AppData" / "Roaming"))
        return Path(base) / "Claude" / "claude_desktop_config.json"
    base = os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))
    return Path(base) / "Claude" / "claude_desktop_config.json"


def deye_server_entry(python_exe: str | None = None) -> dict:
    """The stdio MCP server entry Claude clients use to launch D-Eye locally."""
    return {"command": python_exe or sys.executable, "args": ["-m", "deye.mcp_server"]}


def merge_config(existing_text: str | None, entry: dict) -> dict:
    """Merge the deye entry into existing config text without dropping other servers."""
    data: dict = {}
    if existing_text:
        try:
            data = json.loads(existing_text) or {}
        except json.JSONDecodeError:
            data = {}
    servers = data.setdefault("mcpServers", {})
    changed = servers.get("deye") != entry
    servers["deye"] = entry
    return {"data": data, "changed": changed}


def write_desktop_config(python_exe: str | None = None, *, dry_run: bool = False,
                         path: Path | None = None) -> dict:
    """Write (merging) the deye entry into the Claude Desktop config."""
    path = path or claude_desktop_config_path()
    entry = deye_server_entry(python_exe)
    existing = path.read_text() if path.exists() else None
    merged = merge_config(existing, entry)
    if dry_run:
        return {"path": str(path), "changed": merged["changed"],
                "would_write": merged["data"], "dry_run": True}
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        backup = path.with_name(path.name + f".{stamp}.bak")
        shutil.copy2(path, backup)
    path.write_text(json.dumps(merged["data"], indent=2) + "\n")
    return {"path": str(path), "backup": str(backup) if backup else None,
            "changed": merged["changed"], "server": entry}


def claude_code_command(python_exe: str | None = None) -> list[str]:
    return ["claude", "mcp", "add", "--scope", "user", "deye", "--",
            python_exe or sys.executable, "-m", "deye.mcp_server"]


def add_to_claude_code(python_exe: str | None = None, *, run: bool = False) -> dict:
    cmd = claude_code_command(python_exe)
    pretty = " ".join(cmd)
    if not run:
        return {"command": pretty, "ran": False}
    if shutil.which("claude") is None:
        return {"command": pretty, "ran": False, "note": "claude CLI not found on PATH"}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return {"command": pretty, "ran": True, "returncode": proc.returncode,
                "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    except Exception as exc:  # noqa: BLE001
        return {"command": pretty, "ran": False, "error": str(exc)}


def init_claude(python_exe: str | None = None, *, dry_run: bool = False,
                run_claude_code: bool = False) -> dict:
    """Do both registrations and return a machine-readable report."""
    return {
        "claude_desktop": write_desktop_config(python_exe, dry_run=dry_run),
        "claude_code": add_to_claude_code(python_exe, run=run_claude_code),
        "note": "Restart Claude Desktop after this so it reloads MCP servers.",
    }
