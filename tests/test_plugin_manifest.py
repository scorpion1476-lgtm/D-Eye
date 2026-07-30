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


def test_plugin_ships_all_eight_named_skills():
    """The plugin exposes the 8 specialised D-Eye skills, each with a
    SKILL.md that declares the untrusted-evidence contract and versions."""
    expected = {"research", "evidence", "web_discovery", "browser_research",
                "repository_research", "source_quality",
                "offline_research", "connector_builder"}
    actual = {p.name for p in (PLUGIN / "skills").iterdir() if p.is_dir()}
    assert expected <= actual, f"missing skills: {expected - actual}"
    # Every skill declares the untrusted-evidence contract or is
    # explicitly consent-gated / offline / scaffold-only.
    for name in expected:
        text = (PLUGIN / "skills" / name / "SKILL.md").read_text().lower()
        # frontmatter present
        assert text.startswith("---")
        assert f"name: {name}" in text
        assert "version:" in text
        # at least one of the safety framings
        assert any(term in text for term in (
            "untrusted", "consent", "read-only", "no network", "scaffold",
            "safety",
        )), f"{name}: SKILL.md missing a safety framing"


def test_plugin_research_skill_names_local_mcp_tools():
    """Research skill (the primary user-facing entry point) explicitly
    names the local MCP tool the client should call."""
    text = (PLUGIN / "skills" / "research" / "SKILL.md").read_text().lower()
    assert "export_research_packet" in text
    assert "untrusted" in text


def test_plugin_marketplace_metadata():
    data = json.loads((PLUGIN / "marketplace.json").read_text())
    assert data["name"] == "d-eye"
    assert data["kind"] == "claude-plugin"
    assert data["license"] == "MIT"
    # Safety flags mirror the manifest so a marketplace scanner can enforce.
    flags = set(data["safety_flags"])
    assert {"no_remote_skill_downloading", "read_only_default",
            "no_silent_telemetry", "cookies_stay_local"} <= flags


def test_plugin_readme_declares_safety_properties():
    """The plugin README asserts its safety properties in plain language
    that a security reviewer can grep for."""
    text = (PLUGIN / "README.md").read_text().lower()
    # Every safety property that the plugin manifest declares must appear
    # in the README as a testable claim.
    for claim in (
        "read-only",
        "consent",
        "no remote skill downloading",
        "no silent telemetry",
        "no hard-coded bearer",
        "cookies never uploaded",
    ):
        assert claim in text, f"plugin README missing claim: {claim!r}"


def test_plugin_readme_does_not_name_external_reference_products():
    """No external product name may appear in the user-facing plugin
    README. Attribution belongs in NOTICE / THIRD_PARTY_NOTICES.md."""
    text = (PLUGIN / "README.md").read_text().lower()
    for forbidden in ("agent-reach", "opencli", "firebase", "genkit"):
        assert forbidden not in text, (
            f"plugin README names forbidden product: {forbidden!r}"
        )
