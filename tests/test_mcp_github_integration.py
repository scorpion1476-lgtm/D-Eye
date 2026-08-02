"""C09-F003 GitHub MCP integration.

D-Eye's own MCP surface exposes keyless, read-only GitHub repository inspection
as a first-class tool (`repo_inspect`), so an MCP client (e.g. Claude) can
inspect a public repo through D-Eye's hardened fetch path - no token, no hosted
GitHub MCP dependency.

Acceptance: the tool is advertised in the facade tool list, the dispatcher
routes it to the GitHub connector and returns a structured, redacted result,
and (when the mcp SDK is present) it is registered on the FastMCP server.
"""
from __future__ import annotations

import pytest

from deye import mcp_server
from deye.core.provenance import Envelope, Source, Trust


def test_repo_inspect_is_advertised():
    assert "repo_inspect" in mcp_server.TOOLS


def test_repo_inspect_dispatch_routes_to_connector(monkeypatch):
    captured = {}

    def fake_inspect(router, repo):
        captured["repo"] = repo
        return Envelope(
            content="# owner/name\nstars: 42\nA public repository.",
            source=Source(url="https://github.com/owner/name",
                          connector="github_repo", title="owner/name"),
            trust=Trust(origin="public_web", untrusted=True),
        )

    monkeypatch.setattr("deye.app.inspect_repo", fake_inspect)
    out = mcp_server.handle("repo_inspect", {"repo": "owner/name"})
    assert captured["repo"] == "owner/name"
    assert out["repo"] == "owner/name"
    assert out["title"] == "owner/name"
    assert "public repository" in out["content"]
    assert out["url"] == "https://github.com/owner/name"


def test_repo_inspect_registered_on_fastmcp():
    pytest.importorskip("mcp")
    server = mcp_server.build_fastmcp()
    import asyncio
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert "repo_inspect" in names
    assert "semantic_search" in names


def test_live_repo_inspect_through_mcp_facade():
    """Live, keyless GitHub inspection through the MCP dispatcher. Skips if the
    GitHub API is unreachable or rate-limited so it never blocks the core suite."""
    out = mcp_server.handle("repo_inspect", {"repo": "octocat/Hello-World"})
    if out.get("warnings") and any("rate" in str(w).lower() or "failed" in str(w).lower()
                                   for w in out["warnings"]):
        pytest.skip(f"github unreachable/rate-limited: {out['warnings']}")
    if not out.get("content"):
        pytest.skip("github returned no content in this environment")
    assert "octocat/Hello-World".lower() in (out["content"] + out.get("title", "")).lower()
