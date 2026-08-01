# D-Eye - Feature Equivalence Matrix

_Internal record of how each of the 12 catalogue categories maps onto
D-Eye's own modules, tests, and CLI/plugin surface. Row-level status per
feature ID is tracked in the project's governance workbook and summarised
in the "Status, honestly" section of the top-level [README](../README.md);
under the strict evidence rubric, 55 of 167 rows are PRODUCTION READY._

## Category 1 - Setup + lifecycle (8 rows)

| D-Eye feature | Files | Tests | User surface |
|---|---|---|---|
| One-command install | `scripts/install.sh` | `tests/test_lifecycle.py` | `sh scripts/install.sh` |
| Env detection | `deye/lifecycle/__init__.py::env_detect` | `test_env_detect_*` | `deye lifecycle env` |
| Extras discovery | `deye/lifecycle/__init__.py::detect_extras` | `test_detect_extras_*` | `deye lifecycle extras` |
| Config management | `deye/core/config.py` + `deye/lifecycle/portable_config_*` | `test_portable_config_roundtrip` | `deye lifecycle portable-export/import` |
| Update / rollback | `deye/lifecycle/__init__.py::check_update, apply_update, rollback_to` | `test_check_update_*, test_apply_update_dry_run_*` | `deye lifecycle check-update/apply-update/rollback` |
| Health check | `deye/core/router.py::Router.health_all` + `deye/lifecycle::aggregate_report` | `test_router.py, test_aggregate_report_*` | `deye doctor`, `deye lifecycle status` |
| Repair guidance | `deye/lifecycle/__init__.py::repair_guidance` | `test_repair_guidance_*` | `deye lifecycle repair` |
| Portable configuration | `deye/lifecycle/__init__.py::portable_config_export/import` | `test_portable_config_roundtrip` | `deye lifecycle portable-*` |

## Category 2 - Capability router (7 rows)

`deye/core/router.py` + `registry.py` + `policy.py`. Tests in
`tests/test_router.py` + real MCP subprocess integration in
`tests/test_mcp_tool_invocation.py`. Every capability request goes
through the router - no code path bypasses it.

## Category 3 - Internet + content (16 rows)

- Keyless: `deye/connectors/{web_search,web_fetch,rss,github_repo,
  reddit,v2ex,youtube,xueqiu,xiaoyuzhou}.py`.
- Lawful-boundary stubs: `deye/connectors/social_stub.py` (six
  platforms with no lawful keyless read path).
- Optional keyed adapter: an Exa-style adapter in the tree; off by
  default; never on the acceptance path.
- Tests: `test_new_connectors.py, test_new_connectors_batch2.py,
  test_github_connector.py, test_rss_guard.py`.
- Live smoke: `tests/test_live_network_integration.py` (skips
  cleanly in sandboxed environments that block direct DNS).

## Category 4 - Local browser (9 rows)

`deye/browser/__init__.py` (Playwright adapter, opt-in) +
`profiles.py` (named per-session profiles). Tests in
`tests/test_browser.py, test_new_connectors_batch2.py`.

## Category 5 - Semantic research (13 rows)

`deye/research/__init__.py` - SQLite FTS5, fast/deep, domain
filtering, highlights, find_similar, extractive answer +
`deye/research/multi_source.py` for the fan-out orchestrator.
Tests: `test_quality_and_research.py, test_new_connectors_batch2.py`.

## Category 6 - Evidence + quality (14 rows)

`deye/core/{evidence,graph,quality,provenance}.py`. Multi-tenant
scoping tests in `test_evidence_tenant_scoping.py`. Real acceptance
via MCP subprocess tool invocation in `test_mcp_tool_invocation.py`.

## Category 7 - MCP (11 rows)

`deye/mcp_server.py` (local stdio) + `deye/remote.py` (streamable
HTTP). Real subprocess acceptance in
`tests/test_mcp_subprocess_integration.py` +
`tests/test_mcp_tool_invocation.py`.

## Category 8 - Plugin + skills + hooks + marketplace (13 rows)

`plugin/d-eye/` (manifest, marketplace, MCP config, hooks, 4 slash
commands, 8 skills). Real skill implementations in
`deye/skills/*.py`. Tests: `tests/test_plugin_manifest.py,
test_skills.py`.

## Category 9 - GitHub + dev workflow (10 rows)

`.github/workflows/ci.yml` + `scripts/{gen_sbom,gen_changelog,
verify_repo,scan_licences}.py, scripts/install.sh`. Tests:
`tests/test_no_secrets_in_repo.py, test_licences.py`.

## Category 10 - Provider-neutral backend (10 rows)

`deye/backend/__init__.py` (AuthStore, Queue, ObjectStore, RBAC,
JSONLogger, prometheus_text, Lifecycle) + `deye/backend/events.py`
(EventBus). Tests: `test_backend.py, test_new_connectors_batch2.py`.

## Category 11 - Security + supply chain (19 rows)

- `deye/core/{policy,redact}.py` + `deye/connectors/base.py` (SSRF,
  IP pinning, decompression bomb guard, size caps).
- `tests/test_policy_ssrf.py, test_redact.py, test_decompression_guard.py,
  test_rss_guard.py, test_no_secrets_in_repo.py,
  test_no_telemetry_and_no_remote_skills.py, test_licences.py,
  test_pip_audit_osv.py`.
- `scripts/{scan_licences,gen_sbom}.py`, `scripts/run_pip_audit.sh` +
  `docs/DEPENDENCY_AND_LICENCE_POLICY.md`.

## Category 12 - Cross-surface + roadmap (37 rows)

Mirror rows resolve to their referenced primaries above. Roadmap
rows track the remaining external-platform work: signed release,
live Playwright, cross-platform runners, hosted remote MCP, and Claude
cross-surface activation. These are listed in the roadmap section of the
top-level [README](../README.md).

## Improvements over the baseline capabilities we studied

- SSRF gate + DNS-rebind-safe IP pinning (baseline had URL host-
  allowlist only).
- Credential redaction covers header keys as well as value patterns.
- Decompression-bomb guard is incremental (`decompress(body, cap+1)`
  with unconsumed-tail overflow check) - baseline capped only after
  full expansion.
- RSS DOCTYPE guard scans the prolog for entities (baseline scanned
  only the first 8 KiB, bypassable via a large leading comment).
- Router audit trail passes error strings through `redact()` before
  storage (baseline logged raw exception strings).
- 8 specialised skills with real Python implementations; baseline
  shipped only Markdown descriptions.
- Live OSV vulnerability audit (`scripts/run_pip_audit.sh`) - baseline
  had only a placeholder.
- Multi-tenant scoping across evidence + queue + auth (baseline was
  single-tenant).
- Automated licence-drift enforcement (`scripts/scan_licences.py`
  + `tests/test_licences.py`).
- Automated telemetry + remote-skill-download refusal
  (`tests/test_no_telemetry_and_no_remote_skills.py`).
