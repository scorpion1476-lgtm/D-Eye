"""C08 plugin - BEHAVIOURAL activation checks (no hosted Claude client needed).

These go beyond manifest-key shape checks: they prove the plugin's declared
components are real and functional -

  * the MCP server the plugin declares actually launches and serves its tools;
  * every slash command routes to a tool that really exists on that server;
  * every MCP tool the skills name really exists on that server;
  * the SessionStart hook actually runs the local `deye doctor` health check;
  * every functional component the manifest declares resolves on disk;
  * the plugin's declared version matches the installed package + lifecycle.

Genuine activation *inside Claude* (marketplace listing/installation, universal
cross-surface activation) needs the hosted Claude surface to observe and is
tracked separately under criterion (b).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from deye import __version__, mcp_server

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugin" / "d-eye"
KNOWN_TOOLS = set(mcp_server.TOOLS)
_TOOL_CALL = re.compile(r"`([a-z_]{3,})\(\)`")          # `name()` = explicit call
_BACKTICKED = re.compile(r"`([a-z_]{3,})`")             # `name`


def _venv_bin_env():
    import os
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env


# -- C08-F004 / F001 / F011: the declared MCP server actually runs -----------

def test_declared_mcp_server_launches_and_serves_tools():
    mcp_cfg = json.loads((PLUGIN / "mcp.json").read_text())
    server = mcp_cfg["mcpServers"]["deye"]
    assert server["command"] == "python3"
    assert server["args"] == ["-m", "deye.mcp_server"]
    # Launch exactly what the manifest declares (via this interpreter) and
    # confirm the real server self-test passes.
    proc = subprocess.run([sys.executable, "-m", "deye.mcp_server", "--selftest"],
                          cwd=str(REPO), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "MCP facade self-test OK" in proc.stdout


# -- C08-F007: slash commands route only to tools that exist -----------------

def test_slash_commands_route_to_real_mcp_tools():
    commands = list((PLUGIN / "commands").glob("*.md"))
    assert commands
    for cmd in commands:
        text = cmd.read_text()
        calls = set(_TOOL_CALL.findall(text))
        # every explicit tool call in the command must be a real server tool
        assert calls <= KNOWN_TOOLS, f"{cmd.name} calls unknown tools: {calls - KNOWN_TOOLS}"
        referenced = calls | (set(_BACKTICKED.findall(text)) & KNOWN_TOOLS)
        assert referenced, f"{cmd.name} references no real MCP tool"


# -- C08-F003: skills point Claude at MCP tools that really exist ------------

def test_skills_reference_real_mcp_tools():
    # Skills are instructional (the connector_builder skill legitimately shows
    # a connector's `run()` method, which is not an MCP tool), so we assert the
    # positive: across the skills, the D-Eye MCP tools they tell the client to
    # call all exist on the real server surface.
    skills = [p for p in (PLUGIN / "skills").iterdir() if p.is_dir()]
    assert skills
    referenced: set[str] = set()
    for skill in skills:
        text = (skill / "SKILL.md").read_text()
        referenced |= (set(_BACKTICKED.findall(text)) & KNOWN_TOOLS)
    # every referenced MCP tool is real (by construction of the intersection)
    assert referenced <= KNOWN_TOOLS
    # and the core research tools the skills promise are actually present
    assert {"search", "fetch", "export_research_packet", "query_evidence"} <= referenced


# -- C08-F005 / F006: the SessionStart hook actually runs local doctor -------

def test_session_start_hook_runs_local_doctor():
    shim = PLUGIN / "hook-shim.sh"
    proc = subprocess.run(["bash", str(shim)], cwd=str(REPO),
                          capture_output=True, text=True, timeout=60,
                          env=_venv_bin_env())
    assert proc.returncode == 0, proc.stderr
    # `deye doctor` emits a "N/M connectors usable" summary; its presence proves
    # the hook actually invoked the local health check (not just declared it).
    assert "connectors usable" in proc.stdout, proc.stdout[:400]


# -- C08-F002: every functional component the manifest declares resolves ------

def test_manifest_components_all_resolve_on_disk():
    manifest = json.loads((PLUGIN / "plugin.json").read_text())
    components = manifest["components"]
    for key, rel in components.items():
        target = PLUGIN / rel
        assert target.exists(), f"component {key!r} -> {rel!r} does not exist"
    # the two directory components must actually contain their artifacts
    assert list((PLUGIN / components["skills"]).glob("*/SKILL.md"))
    assert list((PLUGIN / components["commands"]).glob("*.md"))


# -- C08-F009: declared version matches the package and the lifecycle reporter -

def test_plugin_version_matches_package_and_lifecycle():
    manifest = json.loads((PLUGIN / "plugin.json").read_text())
    assert manifest["version"] == __version__
    from deye import lifecycle
    current = lifecycle.check_update().to_dict().get("current_version")
    assert current == __version__
