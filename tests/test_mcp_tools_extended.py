"""Extended in-process MCP tool tests for C07-F005 (connector health),
C07-F006 (search tool), C07-F007 (fetch tool), C07-F010 (research
export tool), and C07-F011 (consent gate).

All tests drive the MCP facade's `handle()` dispatch directly. For
the tools that would otherwise hit the network (search, fetch,
research), we monkey-patch the underlying connectors so the tests
stay entirely offline and deterministic. This is the same
in-process-plus-mock pattern the existing test_mcp_facade.py uses.
"""
from __future__ import annotations

import json
import unittest.mock as mock

import pytest

from deye import mcp_server


# ---------------------------------------------------------------------------
# C07-F005 connector_health
# ---------------------------------------------------------------------------


def test_c07_f005_connector_health_returns_router_health_shape():
    out = mcp_server.handle("connector_health", {})
    assert "connectors" in out
    connectors = out["connectors"]
    assert isinstance(connectors, list) and connectors, (
        "connector_health must return a non-empty list of connector reports"
    )
    # Each entry must have the standard health-report shape
    for c in connectors:
        assert "connector" in c or "name" in c, f"bad connector row: {c}"
        assert "status" in c, f"missing status in: {c}"


# ---------------------------------------------------------------------------
# C07-F006 search tool routes via capability=search
# ---------------------------------------------------------------------------


class _FakeEnv:
    def __init__(self, content, artifacts=None):
        self.content = content
        self.artifacts = artifacts or []


def test_c07_f006_search_tool_routes_to_capability_search():
    fake = _FakeEnv("stub search result", [{"type": "search_results", "results": []}])
    with mock.patch.object(mcp_server, "_search", return_value=fake) as m:
        out = mcp_server.handle("search", {"query": "hello"})
    assert m.called
    called_args = m.call_args
    # signature: _search(router, query)
    assert called_args[0][1] == "hello"
    assert out["content"] == "stub search result"
    assert out["artifacts"] == [{"type": "search_results", "results": []}]


# ---------------------------------------------------------------------------
# C07-F007 fetch tool routes via capability=fetch (safe_get under the hood)
# ---------------------------------------------------------------------------


class _FakeSource:
    def __init__(self, url, title):
        self.url = url
        self.title = title


class _FakeFetchEnv:
    def __init__(self, url, title, content, warnings=None):
        self.source = _FakeSource(url, title)
        self.content = content
        self.warnings = warnings or []


def test_c07_f007_fetch_tool_returns_title_url_content_warnings():
    fake = _FakeFetchEnv(
        url="https://ex.example/page",
        title="Example Page",
        content="hello body",
        warnings=["ok"],
    )
    with mock.patch.object(mcp_server, "_fetch", return_value=fake) as m:
        out = mcp_server.handle("fetch", {"url": "https://ex.example/page"})
    assert m.called
    assert out["url"] == "https://ex.example/page"
    assert out["title"] == "Example Page"
    assert out["content"] == "hello body"
    assert out["warnings"] == ["ok"]


# ---------------------------------------------------------------------------
# C07-F010 export_research_packet emits Markdown + source count
# ---------------------------------------------------------------------------


class _FakePacket:
    def __init__(self, md, envelope_count):
        self._md = md
        self.envelopes = list(range(envelope_count))

    def to_markdown(self):
        return self._md


def test_c07_f010_export_research_packet_returns_markdown_and_source_count():
    fake = _FakePacket("# Research packet\n\n## Sources\n\n- one\n", 5)
    with mock.patch.object(mcp_server, "_research", return_value=fake) as m:
        out = mcp_server.handle("export_research_packet",
                                {"query": "topic", "max_sources": 5})
    assert m.called
    kwargs = m.call_args.kwargs
    args = m.call_args.args
    # signature: _research(router, query, max_sources=N)
    assert args[1] == "topic"
    assert kwargs.get("max_sources") == 5
    assert out["markdown"].startswith("# Research packet")
    assert out["source_count"] == 5


def test_c07_f010_export_research_packet_defaults_max_sources_to_three():
    fake = _FakePacket("packet body", 3)
    with mock.patch.object(mcp_server, "_research", return_value=fake) as m:
        mcp_server.handle("export_research_packet", {"query": "topic"})
    assert m.call_args.kwargs.get("max_sources") == 3


# ---------------------------------------------------------------------------
# C07-F011 consent gate: write actions denied by default, permitted with
# explicit consent
# ---------------------------------------------------------------------------


def test_c07_f011_write_actions_denied_by_default():
    from deye.core.policy import ConsentPolicy
    c = ConsentPolicy()
    d = c.permits("browser.click", is_write=True)
    assert d.allowed is False
    assert "consent" in d.reason.lower()


def test_c07_f011_write_actions_allowed_only_with_explicit_grant():
    from deye.core.policy import ConsentPolicy
    c = ConsentPolicy(allow_write=True, granted_actions={"browser.click"})
    assert c.permits("browser.click", is_write=True).allowed is True
    # A different action is still denied even when allow_write=True
    assert c.permits("some.other.write", is_write=True).allowed is False


def test_c07_f011_read_actions_always_permitted():
    from deye.core.policy import ConsentPolicy
    c = ConsentPolicy()
    assert c.permits("web_fetch", is_write=False).allowed is True


# ---------------------------------------------------------------------------
# Bonus: the TOOLS registry lists every stable tool name
# ---------------------------------------------------------------------------


def test_c07_tools_registry_covers_every_documented_tool():
    for name in ("capability_list", "connector_health", "search", "fetch",
                 "extract", "query_evidence", "export_research_packet",
                 "surface_status"):
        assert name in mcp_server.TOOLS, f"{name} missing from TOOLS"
