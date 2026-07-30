# D-Eye - Offline Mode

Set `DEYE_OFFLINE=1` (or export it in your shell profile) and D-Eye
becomes **zero-network**:

- Every connector that requires network reports
  `HealthReport(status="missing", detail="offline mode")`.
- The capability router transparently skips those connectors.
- `deye lifecycle apply-update` and `provision_extra` refuse politely
  with `{"ok": false, "reason": "offline mode ..."}`.
- The CLI, MCP server, evidence store, FTS5 search, extractive answer,
  and multi-tenant lifecycle continue to work over the local corpus.

## What still works offline

- `deye status`, `deye doctor`, `deye lifecycle env|repair|status|backup`.
- `deye evidence QUERY` - substring search over local rows.
- `deye graph` - build entities + claims + contradiction candidates.
- `deye extract` - pure-function HTML → text.
- The local stdio MCP server and its `capability_list`,
  `connector_health`, `query_evidence`, `extract` tools.
- The `offline_research` skill: `invoke("offline_research", ...)`.

## What deliberately does not

- `deye search`, `deye fetch`, `deye research`, `deye repo` - all need
  network. They return connector-level errors rather than silently
  succeeding.
- The remote HTTP MCP server does not start.

## Offline E2E test

`tests/test_offline_e2e.py` proves the invariants above:

- CLI status returns JSON with no network.
- Registry enumerates every connector offline.
- Router.health_all never calls `safe_get` in offline mode (invariant
  enforced by a boom-monkeypatch on `safe_get`).
- Evidence store persists a packet under `DEYE_OFFLINE=1`.
- FTS5 search + extractive answer over seeded evidence.
- Lifecycle env reports `is_offline=True`.
- `check_update` + `provision_extra` refuse cleanly.
- MCP capability listing works offline.

Runs on every CI push and passes on this local sandbox.
