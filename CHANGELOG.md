# Changelog

## 0.2.0 (validated) - second-pass audit remediation
Added
- Persistent SQLite evidence store (`deye/core/evidence.py`); `query_evidence`
  and `deye evidence` are now REAL (were a stub in 0.1.0).
- Remote mode: genuine Streamable-HTTP MCP transport with enforced bearer auth
  (`deye/remote.py`, `deye serve-http`). Local stdio and remote HTTP are now
  clearly separated.
- Result URL deduplication in the research workflow.

Security
- SSRF fetch now uses **connection-level IP pinning** (connects to the vetted
  IP, preserves SNI/cert validation) -- closes the DNS-rebinding/TOCTOU gap that
  0.1.0 documented as residual.
- Added gzip/deflate **decompression-bomb** caps and non-text content-type
  warnings.

Changed / corrected
- Plugin `.mcp.json` uses `python3 -m deye.mcp_server` and drops fragile JSON
  shell-expansion of `DEYE_HOME` (client-unsupported).
- Exa adapter is now explicitly reported as UNIMPLEMENTED optional integration.
- Docker relabelled: separate local-stdio image vs remote-http service; the
  compatibility matrix no longer implies stdio Docker serves Claude web.
- Added `SECURITY.md`, `.gitignore`, `CHANGELOG.md`, remote-deployment guide.

## 0.1.0 - initial vertical slice
Capability router, SSRF/policy guard, provenance envelopes + cited export,
web search/fetch/extract/RSS, MCP facade, CLI, clean plugin, honest matrix.
