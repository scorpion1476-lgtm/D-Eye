"""Honest, machine-readable Claude-surface compatibility.

This deliberately does NOT claim global activation where Anthropic does not
expose the mechanism. Each row states the real integration path and the
smallest unavoidable one-time action. Verify against current Anthropic docs
before relying on any row -- surface capabilities change.
"""

from __future__ import annotations

SURFACES = [
    {
        "surface": "Claude Code CLI",
        "mechanism": "user-scope MCP server (`claude mcp add --scope user deye ...`)",
        "account_wide": False,
        "user_wide": True,
        "per_project_setup": "none once user-scope is configured",
        "local_device": "full (runs on your machine)",
        "one_time_action": "run `deye setup` then add the user-scope MCP entry once",
        "auto_activation": "yes, across all projects for this user",
        "verify": "claude mcp list  |  deye doctor --surfaces",
    },
    {
        "surface": "Claude Desktop",
        "mechanism": "local MCP server entry in Desktop's MCP config",
        "account_wide": False,
        "user_wide": True,
        "per_project_setup": "n/a",
        "local_device": "full (needed for local files / browser edge)",
        "one_time_action": "add the deye stdio server to Desktop MCP settings once",
        "auto_activation": "yes, for this desktop install",
        "verify": "deye doctor  |  Desktop > settings > MCP servers",
    },
    {
        "surface": "Claude Code in Claude Desktop",
        "mechanism": "inherits Desktop/user MCP configuration",
        "account_wide": False,
        "user_wide": True,
        "per_project_setup": "none",
        "local_device": "full",
        "one_time_action": "same as Claude Desktop",
        "auto_activation": "yes",
        "verify": "deye doctor --surfaces",
    },
    {
        "surface": "Claude.ai web Chat / Projects",
        "mechanism": "remote MCP connector (custom connector) at the account level",
        "account_wide": True,
        "user_wide": True,
        "per_project_setup": "connector is available to enable per project/chat",
        "local_device": "none (web sandbox cannot reach your machine)",
        "one_time_action": "deploy the remote deye MCP server, add it as a custom connector once",
        "auto_activation": "available account-wide; a chat/project may still need it toggled on",
        "verify": "connector appears in the web connector list",
    },
    {
        "surface": "Claude Cowork",
        "mechanism": "desktop/local project model -- verify current official availability",
        "account_wide": False,
        "user_wide": True,
        "per_project_setup": "follows the desktop local-project model",
        "local_device": "full where supported",
        "one_time_action": "same local MCP registration as Desktop",
        "auto_activation": "follows Desktop; confirm against current Anthropic docs",
        "verify": "deye doctor --surfaces",
    },
    {
        "surface": "Other MCP clients (Cursor, etc.)",
        "mechanism": "standard MCP (stdio local or remote URL)",
        "account_wide": False,
        "user_wide": True,
        "per_project_setup": "client-dependent",
        "local_device": "depends on client",
        "one_time_action": "add deye as an MCP server in that client",
        "auto_activation": "client-dependent",
        "verify": "the client's MCP/tool list",
    },
]

HONEST_LIMITS = [
    "There is no single button that turns D-Eye on for every Claude surface at once. "
    "Web surfaces use a remote connector; local surfaces use a local MCP server. "
    "Those are two different mechanisms by design.",
    "Web Chat/Projects run in a sandbox and cannot reach your local files, browser "
    "sessions, or terminal. Local-device capabilities require Claude Desktop / Code / "
    "Cowork on your machine.",
    "A remote connector can be made available account-wide, but an individual "
    "project or chat may still require enabling it -- that is an Anthropic UI behaviour, "
    "not something D-Eye can override.",
]


def surface_status() -> dict:
    return {
        "surfaces": SURFACES,
        "honest_limits": HONEST_LIMITS,
        "note": "Verify each row against current Anthropic documentation before relying on it.",
    }
