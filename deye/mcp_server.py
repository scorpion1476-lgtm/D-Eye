"""D-Eye MCP facade.

Exposes a SMALL, stable tool set (forensic 3.5) -- not raw scrapers or shell:

    capability_list, connector_health, search, fetch, extract,
    query_evidence, export_research_packet

If the official `mcp` SDK is installed it runs a real stdio MCP server. If not,
the same handlers are importable/testable directly, and `python -m
deye.mcp_server --selftest` exercises them without the SDK. This keeps the
facade verifiable in constrained environments.
"""

from __future__ import annotations

import json
import sys

from deye.app import build_router
from deye.app import fetch as _fetch
from deye.app import research as _research
from deye.app import search as _search
from deye.core.config import Config
from deye.core.redact import redact
from deye.extract import html_to_text
from deye.surfaces import surface_status

TOOLS = [
    "capability_list", "connector_health", "search", "fetch",
    "extract", "query_evidence", "export_research_packet", "surface_status",
    "semantic_search", "repo_inspect",
]


def _router():
    return build_router(Config.load())


def handle(tool: str, args: dict) -> dict:
    """Pure dispatch -- unit-testable without any MCP transport."""
    if tool == "capability_list":
        return {"capabilities": _router().registry.capabilities(), "tools": TOOLS}
    if tool == "connector_health":
        return {"connectors": _router().health_all()}
    if tool == "surface_status":
        return surface_status()
    if tool == "search":
        env = _search(_router(), args["query"])
        return {"content": redact(env.content), "artifacts": env.artifacts}
    if tool == "fetch":
        env = _fetch(_router(), args["url"])
        return {"title": env.source.title, "url": env.source.url,
                "content": redact(env.content[:8000]), "warnings": env.warnings}
    if tool == "extract":
        return {"text": html_to_text(args.get("html", ""))}
    if tool == "export_research_packet":
        packet = _research(_router(), args["query"], max_sources=args.get("max_sources", 3))
        return {"markdown": redact(packet.to_markdown()),
                "source_count": len(packet.envelopes)}
    if tool == "query_evidence":
        from deye.app import query_evidence
        return query_evidence(args.get("query", ""))
    if tool == "semantic_search":
        from deye.app import semantic_answer
        return semantic_answer(args["query"], k=int(args.get("k", 5)))
    if tool == "repo_inspect":
        from deye.app import inspect_repo
        env = inspect_repo(_router(), args["repo"])
        return {"repo": args["repo"], "title": env.source.title,
                "url": env.source.url, "content": redact(env.content[:8000]),
                "warnings": env.warnings}
    raise ValueError(f"unknown tool: {tool}")


def _selftest() -> int:
    print(json.dumps(handle("capability_list", {}), indent=2))
    print(json.dumps(handle("connector_health", {}), indent=2))
    print(json.dumps(handle("surface_status", {})["honest_limits"], indent=2))
    print("MCP facade self-test OK")
    return 0


def build_fastmcp():
    """Construct the FastMCP server with the stable tool surface. Shared by the
    stdio (local) and streamable-http (remote) transports."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("deye")

    @server.tool()
    def capability_list() -> dict:
        return handle("capability_list", {})

    @server.tool()
    def connector_health() -> dict:
        return handle("connector_health", {})

    @server.tool()
    def search(query: str) -> dict:
        return handle("search", {"query": query})

    @server.tool()
    def fetch(url: str) -> dict:
        return handle("fetch", {"url": url})

    @server.tool()
    def extract(html: str) -> dict:
        return handle("extract", {"html": html})

    @server.tool()
    def export_research_packet(query: str, max_sources: int = 3) -> dict:
        return handle("export_research_packet", {"query": query, "max_sources": max_sources})

    @server.tool()
    def query_evidence(query: str) -> dict:
        return handle("query_evidence", {"query": query})

    @server.tool()
    def surface_status() -> dict:
        return handle("surface_status", {})

    @server.tool()
    def semantic_search(query: str, k: int = 5) -> dict:
        return handle("semantic_search", {"query": query, "k": k})

    @server.tool()
    def repo_inspect(repo: str) -> dict:
        return handle("repo_inspect", {"repo": repo})

    return server


def run_stdio() -> int:  # pragma: no cover - requires mcp SDK + a client
    try:
        server = build_fastmcp()
    except Exception:
        sys.stderr.write(
            "The `mcp` SDK is not installed. Install with `pip install 'deye[mcp]'` "
            "or run `python -m deye.mcp_server --selftest`.\n"
        )
        return 2
    server.run()
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    sys.exit(run_stdio())
