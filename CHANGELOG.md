# Changelog

## 0.3.0-dev (unreleased) - Phase B: security hardening & supply chain (2026-07-29)
Security
- Credential redaction: `redact_mapping` now redacts by credential *header key*
  (Authorization/Cookie/X-Api-Key/…) - value-only scanning leaked `Basic`/`Token`/
  `Digest` auth and API keys. Inline `authorization` pattern captures the whole
  credential, not just the scheme word.
- Decompression-bomb guard: bounded incremental decompression
  (`zlib.decompressobj().decompress(body, cap+1)`) - the previous cap ran only
  after `gzip.decompress()` fully expanded the body, allowing a small gzip bomb
  to OOM the process.
- RSS/Atom DOCTYPE guard: replaced the 8 KiB-window scan (bypassable with a large
  leading comment) with a prolog scanner that skips decls/PIs/comments of any
  length and does not false-positive on `<!DOCTYPE` inside CDATA content.
- Router audit trail redacts connector error messages before logging.
Fixed
- Pinned `mcp[cli]>=1.0,<2` (2.0.0 renamed `FastMCP`→`MCPServer`, breaking the
  MCP server import); CI installs the `[remote]` extra so the pin is authoritative.
- Robust in-repo secret scan (skips venv/VCS/build/binaries); UTC-aware backup
  timestamps; `re.split` maxsplit keyword (py3.13+ deprecation).
Tests: 69 passed / 1 skipped (core), 73 passed / 0 skipped (mcp). bandit 0, pip-audit 0.

## 0.3.0-dev (unreleased) - Phase A: evidence graph, connectors, security CI
Added
- Evidence graph + contradiction detection (`deye/core/graph.py`, `deye graph`):
  entities and claims over stored evidence, with polarity and numeric
  contradiction candidates carrying confidence scores. Heuristic, not a learned
  NLI model; findings are leads for human review.
- Read-only GitHub research connector (`deye/connectors/github_repo.py`,
  `deye repo`, capability `repo.inspect`) using the public REST API through the
  existing SSRF-guarded, connection-pinned fetch path.
- Real Exa adapter (`ExaSearch` in `deye/connectors/web_search.py`):
  authenticated POST, contents + highlights, domain include/exclude, date
  filters, find-similar and answer modes, cost reporting, and keyless fallback
  when no `EXA_API_KEY` is configured. Not yet verified against the live Exa API.
- `safe_post` in `deye/connectors/base.py`: policy-gated, connection-pinned POST
  (single-hop; refuses to follow redirects) reusing the decompression caps.
- SBOM generator (`scripts/gen_sbom.py`): CycloneDX 1.5 JSON, declared and
  installed-environment modes.
- CI workflow (tests across core/mcp extras + lint + SBOM) and a Security
  workflow (bandit SAST, secret scan, pip-audit, dependency review, SBOM),
  both with least-privilege `contents: read`.

Security
- XXE / entity-expansion guard on RSS/Atom parsing (`_safe_fromstring` rejects
  DOCTYPE declarations); clears the bandit MEDIUM. Bandit now reports 0 issues.

Tests
- Phase A introduced 62 passed / 1 skipped (core) and these new suites:
  `test_graph.py`, `test_github_connector.py`, `test_exa_adapter.py`,
  `test_rss_guard.py`. Superseded by the Phase B totals above
  (**69 passed / 1 skipped** core; **73 passed / 0 skipped** with MCP extras).

## 0.2.0 (validated) - second-pass audit remediation
Added
- Persistent SQLite evidence store (`deye/core/evidence.py`); `query_evidence`
  and `deye evidence` are now REAL (were a stub in 0.1.0).
- Remote mode: genuine Streamable-HTTP MCP transport with enforced bearer auth
  (`deye/remote.py`, `deye serve-http`). Local stdio and remote HTTP are now
  clearly separated.
- Result URL deduplication in the research workflow.
- `deye init-claude`: one-command registration into Claude Desktop and Claude
  Code (OS-aware config path, backup-before-write, merge without clobbering
  other servers, `--dry-run` preview).
- `scripts/install.sh`: single-step venv install + setup + Claude registration
  for non-technical users.

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
- Corrected the test-count in the README repository-layout section (now 51) and
  refreshed `docs/TEST_REPORT.md` to the full-suite run (51 passed with the
  optional mcp/starlette extras; 47 passed + 4 skipped without them).

## 0.1.0 - initial vertical slice
Capability router, SSRF/policy guard, provenance envelopes + cited export,
web search/fetch/extract/RSS, MCP facade, CLI, clean plugin, honest matrix.
