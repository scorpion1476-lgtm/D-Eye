from deye.mcp_server import handle, TOOLS

def test_capability_list():
    out = handle("capability_list", {})
    assert "search" in out["capabilities"]
    # The facade must expose exactly the stable tool surface, no more, no less.
    expected = {
        "capability_list", "connector_health", "search", "fetch",
        "extract", "query_evidence", "export_research_packet", "surface_status",
    }
    assert set(TOOLS) == expected
    assert out["tools"] == TOOLS

def test_connector_health_shape():
    out = handle("connector_health", {})
    assert isinstance(out["connectors"], list) and out["connectors"]

def test_extract_tool():
    assert "Hi" in handle("extract", {"html": "<p>Hi</p>"})["text"]

def test_surface_status_is_honest():
    out = handle("surface_status", {})
    assert any("no single button" in l for l in out["honest_limits"])
