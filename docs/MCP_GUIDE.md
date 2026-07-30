# D-Eye — MCP Guide

D-Eye ships a stable MCP tool surface across two transports:

- **local stdio** — recommended for Claude Desktop, Claude Code, and
  any locally-running MCP client.
- **remote streamable-HTTP** — for cross-network clients; bearer-auth
  required.

## Stable tools

Every transport exposes the same 8 tools:

| Tool | Purpose |
|---|---|
| `capability_list` | Enumerate every registered capability + tool name. |
| `connector_health` | Report per-connector status (`ok`, `degraded`, `missing`, `broken`). |
| `search` | Route a search request through the capability router. |
| `fetch` | Fetch one URL through the SSRF-guarded path + extract text. |
| `extract` | Convert an HTML string to readable text (pure function). |
| `query_evidence` | Query the persistent evidence store. |
| `export_research_packet` | Search → fetch top N → cite → persist. |
| `surface_status` | Report which Claude surfaces D-Eye can reach. |

## Local stdio MCP

Install:

```bash
./.venv/bin/python -m pip install -e '.[mcp]'
```

Register with Claude Desktop + Code:

```bash
./.venv/bin/deye init-claude              # writes config
./.venv/bin/deye init-claude --run-claude-code
./.venv/bin/deye init-claude --dry-run    # preview only
```

Verify it's live:

```bash
./.venv/bin/deye doctor --surfaces
```

Restart Claude Desktop for it to pick up the new server entry.

## Remote streamable-HTTP MCP

Install:

```bash
./.venv/bin/python -m pip install -e '.[remote]'
```

Run behind a TLS-terminating reverse proxy (recommended: caddy or nginx):

```bash
export DEYE_HTTP_TOKEN="a-long-random-secret-32-bytes-minimum"
./.venv/bin/deye serve-http --host 0.0.0.0 --port 8080
```

Client requests must include `Authorization: Bearer $DEYE_HTTP_TOKEN`.
Requests without a valid token receive 401.

## Container deployment

`docker/Dockerfile` runs D-Eye as a non-root user. `docker/docker-compose.yml`
provides a single-node spec:

```bash
cd docker
DEYE_HTTP_TOKEN="..." docker compose up -d
```

Put a reverse proxy in front for TLS termination.

## Client registration in Claude cloud surfaces

**User-owned action.** Registering a remote MCP endpoint as a connector
inside a Claude tenant (Claude web, Projects, Cowork) is a security-
critical action performed by the account owner via the Claude UI or
the tenant's admin API. D-Eye ships the endpoint the tenant consumes
but cannot silently register itself into a third-party account. See
[`CLAUDE_SURFACE_SUPPORT.md`](CLAUDE_SURFACE_SUPPORT.md).

## Real MCP subprocess acceptance tests

The test suite spawns `python -m deye.mcp_server` as a real subprocess
and drives a real JSON-RPC handshake over stdio + real `tools/call` for
`capability_list`, `extract`, and `query_evidence`. See
`tests/test_mcp_tool_invocation.py`.
