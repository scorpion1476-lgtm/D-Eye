import pytest

pytest.importorskip("mcp")
pytest.importorskip("starlette")
from starlette.testclient import TestClient
from deye.remote import build_app

TOKEN = "test-token-1234567890"

def test_healthz_open():
    with TestClient(build_app(TOKEN)) as c:
        r = c.get("/healthz")
    assert r.status_code == 200 and r.text == "ok"

def test_mcp_requires_auth():
    with TestClient(build_app(TOKEN)) as c:
        r = c.post("/mcp/", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
    assert r.status_code == 401

def test_mcp_wrong_token_rejected():
    with TestClient(build_app(TOKEN)) as c:
        r = c.post("/mcp/", headers={"Authorization": "Bearer wrong"},
                   json={"jsonrpc": "2.0", "method": "ping", "id": 1})
    assert r.status_code == 401

def test_mcp_valid_token_passes_auth():
    # With the app lifespan running (context manager), a correctly-authenticated
    # request clears OUR middleware and reaches the MCP layer -> not 401.
    with TestClient(build_app(TOKEN)) as c:
        r = c.post("/mcp/",
                   headers={"Authorization": f"Bearer {TOKEN}",
                            "Accept": "application/json, text/event-stream",
                            "Content-Type": "application/json"},
                   json={"jsonrpc": "2.0", "method": "initialize", "id": 1,
                         "params": {"protocolVersion": "2025-03-26",
                                    "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}})
    assert r.status_code != 401
