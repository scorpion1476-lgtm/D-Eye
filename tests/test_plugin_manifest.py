"""Acceptance tests for the Claude plugin at `plugin/d-eye/`.

Validates: manifest structure, MCP server config, hook config,
slash-command definitions, marketplace metadata, safety-flag
enforcement (no remote-skill downloading, no telemetry, read-only
default). All checks are file-based; no Claude Code is needed.

Covers Category 8 rows (plugin, plugin manifest, skill instructions,
MCP configuration, session-start hook, health hook, slash commands,
marketplace, MCPB packaging).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent / "plugin" / "d-eye"


def test_plugin_manifest_shape():
    data = json.loads((PLUGIN / "plugin.json").read_text())
    assert data["name"] == "d-eye"
    assert data["version"]
    assert data["license"] == "MIT"
    # every safety flag is asserted true — this is a testable property, not
    # documentation prose.
    safety = data["safety"]
    for flag in ("read_only_default", "no_remote_skill_downloading",
                 "no_silent_telemetry", "consent_required_for_writes",
                 "cookies_never_uploaded"):
        assert safety.get(flag) is True, f"safety flag {flag} not True"


def test_plugin_mcp_config_shape():
    data = json.loads((PLUGIN / "mcp.json").read_text())
    assert "mcpServers" in data
    deye = data["mcpServers"].get("deye")
    assert deye is not None
    assert deye["command"] == "python3"
    assert deye["args"] == ["-m", "deye.mcp_server"]
    # No bearer token / API key baked into the plugin.
    assert "token" not in json.dumps(deye).lower()
    assert "api_key" not in json.dumps(deye).lower()


def test_plugin_slash_commands_present_and_wellformed():
    commands_dir = PLUGIN / "commands"
    assert commands_dir.is_dir()
    names = {f.stem for f in commands_dir.glob("*.md")}
    assert names >= {"deye-research", "deye-fetch", "deye-doctor",
                     "deye-evidence"}
    # every command file starts with YAML frontmatter
    for cmd in commands_dir.glob("*.md"):
        text = cmd.read_text()
        assert text.startswith("---")
        assert "name:" in text.splitlines()[1]
        assert "description:" in text
        # never invoke an external service directly
        assert "curl" not in text
        assert "http://" not in text
        # every command routes through the `deye` MCP server
        assert "deye" in text.lower()


def test_plugin_session_start_hook_is_local_only():
    data = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())
    assert "SessionStart" in data["hooks"]
    # Only hook shape allowed is a local shell command; no network URLs.
    for entry in data["hooks"]["SessionStart"]:
        for h in entry["hooks"]:
            assert h["type"] == "command"
            cmd = h["command"]
            # no remote downloads inside the hook command literal
            assert "curl" not in cmd
            assert "wget" not in cmd
            assert "http://" not in cmd
            assert "https://" not in cmd


def test_plugin_hook_shim_is_local_and_read_only():
    shim = (PLUGIN / "hook-shim.sh").read_text()
    # No network egress inside the shim.
    for banned in ("curl ", "wget ", "http://", "https://", "nc "):
        assert banned not in shim, f"hook-shim contains banned token: {banned}"
    # Only calls the local deye CLI.
    assert "deye doctor" in shim


def test_plugin_skill_declares_untrusted_evidence_contract():
    skill = (PLUGIN / "skills" / "deye" / "SKILL.md").read_text().lower()
    assert "untrusted" in skill
    # skill points to the local MCP tools
    for tool in ("search", "fetch", "export_research_packet"):
        assert tool in skill


def test_plugin_marketplace_metadata():
    data = json.loads((PLUGIN / "marketplace.json").read_text())
    assert data["name"] == "d-eye"
    assert data["kind"] == "claude-plugin"
    assert data["license"] == "MIT"
    # Safety flags mirror the manifest so a marketplace scanner can enforce.
    flags = set(data["safety_flags"])
    assert {"no_remote_skill_downloading", "read_only_default",
            "no_silent_telemetry", "cookies_stay_local"} <= flags


def test_plugin_readme_documents_deltas_from_reference():
    text = (PLUGIN / "README.md").read_text().lower()
    # Explicit callout that reference-plugin behaviours were removed.
    assert "hard-coded bearer" in text or "no hard-coded" in text
    assert "session" in text  # session-start behaviour discussed
    assert "telemetry" in text
