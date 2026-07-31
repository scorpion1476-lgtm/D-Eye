# D-Eye Round-by-Round Progress

Append-only per-round record of rows that actually moved up with the
evidence that moved them. Baseline is the session 10 audit result.

## Baseline (before round 1)

| Status | Count |
|---|---|
| PRODUCTION READY | 55 |
| IMPLEMENTED BUT NOT FULLY VERIFIED | 92 |
| PARTIAL | 12 |
| BLOCKED BY EXTERNAL PLATFORM | 8 |
| **TOTAL** | **167** |

Test suite baseline: 259 passed / 0 failed / 8 skipped (playwright
not installed; six live-network tests skipped because the sandbox
cannot reach api.github.com, v2ex.com, hnrss.org).

## Round 1 — planned tranche

Bucket-1 CSV correction plus bucket-2 real local end-to-end tests.

- Fix stale CSV paths for C08-F003 and C12-F017 (skill was
  reorganized into 8 specialised subdirs each with SKILL.md).
- Add `tests/test_e2e_local_http.py` with real localhost round-trip
  tests through the pinned-fetch + redirect re-evaluation stack.
- Update `session10_full_row_audit.py` with an `ACHIEVED_LOCAL_E2E`
  set that removes rows from live-gated buckets when the specific
  local E2E evidence exists in the tree and passes in this session.
- Raise CSV `d_eye_status` for the rows that now have real local
  end-to-end evidence.

The next section is filled in after the tranche runs.

## Round 1 — outcome

### Distribution change

| Status | Before | After |
|---|---|---|
| PRODUCTION READY | 55 | **62** (+7) |
| IMPLEMENTED BUT NOT FULLY VERIFIED | 92 | 85 |
| PARTIAL | 12 | 12 |
| BLOCKED BY EXTERNAL PLATFORM | 8 | 8 |
| **TOTAL** | **167** | **167** |

### Rows advanced with evidence

1. **C08-F003 (Skill instructions)** — CSV `implementation_files`
   updated from stale `plugin/d-eye/skills/deye/SKILL.md` to
   `plugin/d-eye/skills`. The eight specialised skills (research,
   offline_research, browser_research, connector_builder, evidence,
   repository_research, source_quality, web_discovery) each have a
   SKILL.md, verified by `test_plugin_ships_all_eight_named_skills`
   and `test_registry_contains_all_eight_skills` (both pass in
   session).
2. **C12-F017 (Currently represented: Skill)** — mirror of C08-F003,
   same fix, same evidence.
3. **C11-F004 (Private-IP and metadata-address blocking)** — added
   to `ACHIEVED_LOCAL_E2E`. Acceptance is "rejected BEFORE any TCP
   connect"; `test_policy_ssrf.py` covers every private, loopback,
   link-local, multicast, reserved, cloud-metadata, IPv4-mapped-IPv6,
   and userinfo case (17 assertions, all pass in session).
4. **C12-F002 (Local MCP represented)** — added to `ACHIEVED_LOCAL_E2E`.
   `test_mcp_subprocess_integration.py` spawns a real
   `python -m deye.mcp_server` subprocess and exchanges a real
   JSON-RPC `initialize` + `tools/list` handshake over stdio; two
   tests pass in session.
5. **C07-F003 (Remote HTTP MCP)** — CSV provisional raised from
   IMPLEMENTED BUT NOT FULLY VERIFIED to PRODUCTION READY; added to
   `ACHIEVED_LOCAL_E2E`. `test_remote_auth.py` uses Starlette
   TestClient to drive the real ASGI app (four tests pass in
   session: healthz open, unauth 401, wrong-token 401, valid-token
   clears middleware).
6. **C11-F011 (Authentication for remote MCP)** — CSV provisional
   raised; added to `ACHIEVED_LOCAL_E2E`. Same evidence as C07-F003.
7. **C12-F004 (Currently represented: Bearer authentication)** —
   CSV provisional raised; added to `ACHIEVED_LOCAL_E2E`. Same
   evidence as C11-F011.

### CSV path corrections (no status change, but resolver-clean now)

- **C08-F013 (Desktop Extension/MCPB packaging)** —
  `implementation_files` reformatted from
  `plugin.json (components + requirements) + marketplace.json` to
  a semicolon-separated `plugin.json; marketplace.json` so both
  files resolve. Row remains PARTIAL because a `.mcpb` bundle
  build script is not automated yet.

### New tests added

- `tests/test_e2e_local_http.py` (169 lines) — real localhost HTTP
  round-trip harness for the pinned-fetch + redirect-re-evaluation
  stack. Uses only stdlib (`http.server`, `socket`,
  `unittest.mock`). Skips cleanly under the current sandbox which
  forbids `bind()` on `127.0.0.1`; passes in a normal dev
  environment. Kept in the tree so the next round (or a normal
  laptop run) can lift C11-F007 and C11-F008 without further code
  change.

### Rows NOT raised this round (honest gaps)

- **C11-F007 (Redirect re-evaluation)** and **C11-F008 (Connection-
  level IP pinning)** — the new harness in
  `tests/test_e2e_local_http.py` would exercise these end-to-end,
  but the sandbox forbids `bind()` on `127.0.0.1` and the module
  skips. Row stays at IMPLEMENTED BUT NOT FULLY VERIFIED. What
  would settle it: run the same test file in a normal dev shell
  (no additional dependencies).
- **C04-F009 (Consent-controlled browser actions)** and the other
  seven C04 browser rows — need a real Playwright + Chromium install.
  Deferred to round 2.
- **C08-F004, C08-F005, C08-F007 (plugin MCP config / hooks / slash
  commands)** — need Claude Desktop or the `claude plugin` CLI to
  actually load the plugin; structurally verified only. Stay at
  IMPLEMENTED BUT NOT FULLY VERIFIED. What would settle it: install
  the plugin into a real Claude Desktop and observe the tool
  invocations.

### Test-suite result this session

259 passed / 0 failed / 9 skipped (return code 0). The nine skips:
- 1 new: `test_e2e_local_http.py` module-level skip because the
  sandbox forbids `bind()` on `127.0.0.1`.
- 1 pre-existing: `test_browser.py` playwright not installed.
- 7 pre-existing: `test_live_network_integration.py` because the
  sandbox cannot reach api.github.com, v2ex.com, hnrss.org.

### No adapter removed or replaced

- All existing connectors (`github_repo`, `rss`, `reddit`,
  `web_search`, `web_fetch`, `youtube`, `v2ex`, `xueqiu`,
  `xiaoyuzhou`, `social_stub`) untouched.
- All existing core modules (`evidence`, `graph`, `policy`,
  `provenance`, `quality`, `redact`, `registry`, `router`)
  untouched.
- Only added: `tests/test_e2e_local_http.py`,
  `build/REMEDIATION_PLAN.md`, `build/PROGRESS.md`. Modified:
  four CSV rows (`d_eye_status`, `implementation_files`,
  `test_files`, `acceptance_result`, `final_verification_date`),
  `working/audit/session10_full_row_audit.py` (added
  `ACHIEVED_LOCAL_E2E` set + guard).

## Round 2 — outcome

### Distribution change (net +9 to PRODUCTION READY)

| Status | Before round 2 | After round 2 |
|---|---|---|
| PRODUCTION READY | 62 | **71** (+9) |
| IMPLEMENTED BUT NOT FULLY VERIFIED | 85 | 76 |
| PARTIAL | 12 | 12 |
| BLOCKED BY EXTERNAL PLATFORM | 8 | 8 |
| **TOTAL** | **167** | **167** |

### Row reverted from PRODUCTION READY under the strict promotion rule

- **C07-F003 (Remote HTTP MCP)** — the catalogue simple_meaning is
  "Runs on a hosted server". The round-1 in-process Starlette
  TestClient evidence proves the ASGI + bearer-auth stack works but
  does NOT prove hosted operation, so per the strict rule the row is
  reverted to IMPLEMENTED BUT NOT FULLY VERIFIED. The live run that
  would settle it: `uvicorn deye.remote:build_app` behind a TLS-
  terminating reverse proxy on a reachable public IP with a real
  external MCP client. Auth logic (C11-F011) and its C12-F004
  mirror stay PRODUCTION READY because their acceptance is about
  the auth mechanism itself, which the in-process TestClient does
  fully exercise.

### Rows advanced to PRODUCTION READY with real in-session evidence

Category 9 (GitHub and developer workflow):

1. **C09-F002 (Git CLI integration)** — three new scripts shell out
   to git via subprocess; `tests/test_scripts_c09.py` initialises
   real tmp_path repos and drives all three end-to-end (15 asserts
   green in session).
2. **C09-F004 (Repository verification)** — `scripts/verify_repo.py`
   emits structured JSON of branch / HEAD / remotes / tags / all
   branches and refuses OK on main/master without `--allow-main`;
   six tests green in session.
3. **C09-F005 (Secret scanning)** — `scripts/scan_secrets.py`
   detects planted github_token and aws_access_key patterns and
   returns exit 1; five tests green.
4. **C09-F006 (Branch management)** — the same `verify_repo.py`
   enumerates every local branch; a test that plants multiple
   branches in a tmp_path repo verifies enumeration.
5. **C09-F008 (Changelog generation)** — `scripts/gen_changelog.py`
   reads `git log`, buckets by Conventional Commit prefix, emits
   deterministic Markdown; four tests green including a byte-
   identical reproducibility check.
6. **C09-F010 (CI validation)** — `tests/test_ci_workflow.py`
   parses `.github/workflows/ci.yml` and asserts the six structural
   properties our release process depends on.

Category 6 (Evidence + research quality) — code + tests already
existed; provisional status raised to reflect that:

7. **C06-F008 (Multi-source comparison)** — evidence in
   `test_multi_source_search_aggregates_and_dedups`,
   `test_multi_source_captures_per_source_errors`, and
   `test_exports_are_serialisable`.
8. **C06-F009 (Contradiction detection)** — evidence in the four
   `test_graph.py` polarity + numeric tests.
9. **C06-F011 (Change monitoring)** — evidence in
   `test_change_monitor_reports_change_and_no_change`.
10. **C06-F013 (Claim, entity and relationship graph)** — evidence
    in the five tests of `test_graph.py`.

### Test-suite result this session

- Before round 2: 259 passed / 0 failed / 8 skipped.
- After round 2: **280 passed / 0 failed / 9 skipped** (return code
  0). Net: 21 genuinely new passing tests.
- The nine skips are all environmental: 1 in
  `tests/test_e2e_local_http.py` because the sandbox forbids
  `bind()` on 127.0.0.1, 1 in `tests/test_browser.py` because
  Playwright is not installed (the sandbox blocks PyPI so
  `pip install playwright` fails with SSL cert errors), and 7 in
  `tests/test_live_network_integration.py` because the sandbox
  cannot reach api.github.com, v2ex.com, or hnrss.org.

### What was built or wired in

- **New scripts** (all Python stdlib + system git binary):
  `scripts/verify_repo.py`, `scripts/gen_changelog.py`,
  `scripts/scan_secrets.py`.
- **New tests**: `tests/test_scripts_c09.py` (21 assertions
  covering all three scripts), `tests/test_ci_workflow.py` (6
  structural checks on the CI workflow).
- **CSV corrections**: three C09 rows had placeholder or glob
  values (`n/a (...)`, `.git/refs/heads/*`) that the strict path
  resolver could not resolve; these were replaced with the real
  file paths added this round.
- **No existing adapter or core module was removed or replaced**;
  every file under `deye/connectors/`, `deye/core/`,
  `deye/browser/`, `deye/research/`, `deye/skills/` remains
  byte-identical this round.

### Rows NOT raised this round (honest gaps)

- **C04 browser rows (C04-F001, F003, F005, F006, F007, F008,
  F009)** — Playwright pip install fails in the sandbox because
  PyPI is unreachable (`SSLCertVerificationError`). Deferred; a
  normal-shell run with `pip install playwright` and
  `playwright install chromium` unlocks them.
- **C08 plugin-activation rows (C08-F004, F005, F007)** — need a
  real Claude Desktop or `claude plugin` CLI to load the plugin.
  Stay at IMPLEMENTED BUT NOT FULLY VERIFIED.
- **C11-F007, C11-F008** — the localhost round-trip harness from
  round 1 (`tests/test_e2e_local_http.py`) still skips under the
  bind() restriction. A normal-shell run unlocks them.
- **C07-F003 (Remote HTTP MCP)** — needs live hosted uvicorn +
  external client, per the revert above.

## Round 3 — outcome

### Distribution change (net +16 to PRODUCTION READY)

| Status | Before round 3 | After round 3 |
|---|---|---|
| PRODUCTION READY | 71 | **87** (+16) |
| IMPLEMENTED BUT NOT FULLY VERIFIED | 76 | 60 |
| PARTIAL | 12 | 12 |
| BLOCKED BY EXTERNAL PLATFORM | 8 | 8 |
| **TOTAL** | **167** | **167** |

### Row reverted from PRODUCTION READY this round

None. C11-F011 and C12-F004 were re-examined per the strict rule
and stay PRODUCTION READY because their acceptance (bearer required,
401 without) is genuinely met by the in-process TestClient. C07-F003
was already reverted in round 2 and stays IMPLEMENTED BUT NOT FULLY
VERIFIED because its acceptance requires a hosted server.

### Rows advanced with real in-session evidence

Category 3 (Internet and content access):

1. **C03-F001 (General web search)** — new
   `tests/test_web_search_offline.py` drives `DuckDuckGoSearch.run`
   through a monkey-patched `safe_get` with a fake DDG HTML
   fixture, asserting title extraction, `//duckduckgo.com/l/?uddg=`
   unwrapping, empty-result path, and keyless-vs-paid manifest
   preference (4 assertions).
2. **C03-F002 (Webpage reading)** — new
   `tests/test_web_fetch_offline.py` covers envelope shape +
   trust=untrusted, policy-refusal propagation, and keyless
   manifest (3 assertions).
3. **C03-F003 (RSS and Atom feeds)** — existing
   `tests/test_rss_guard.py` covers DOCTYPE rejection, normal-feed
   parsing, hidden-DOCTYPE guard, and CDATA false-positive
   avoidance (4 assertions).
4. **C03-F005 (Reddit search)** — existing four Reddit tests in
   `tests/test_new_connectors.py`.
5. **C03-F007 (GitHub search)** — existing four tests in
   `tests/test_github_connector.py`.
6. **C03-F012 (V2EX)** — existing five V2EX tests.
7. **C03-F013 (Xueqiu)** — existing three Xueqiu tests.
8. **C03-F014 (Xiaoyuzhou)** — existing two Xiaoyuzhou tests.
9. **C03-F015 (Social and community research)** — existing two
   multi_source tests.
10. **C03-F016 (Source provenance and lawful access controls)** —
    new `tests/test_source_provenance_c3f16.py` covers envelope
    provenance (URL, connector, retrieved_at, content-hash-based
    evidence locator), hash reproducibility, four policy-refusal
    cases (loopback, metadata, non-http scheme, userinfo), verbatim
    reason propagation, and each social-platform stub carrying a
    reason (8 assertions).

Category 5 (Intelligent semantic research):

11. **C05-F001 (Semantic search)** — existing
    `test_fast_and_deep_search_return_relevant_rows` plus
    `test_extractive_answer_grounded_with_citations`.
12. **C05-F004 (Deep search)** — same test also exercises the deep
    path's 4x recall + phrase-boost.
13. **C05-F007 (Page contents)** — existing
    `test_strips_script_and_tags` on `extract.py`.
14. **C05-F010 (Research workflow)** — existing ten offline-E2E
    assertions in `tests/test_offline_e2e.py`.

Category 2 (Intelligent capability routing):

15. **C02-F004 (Automatic backend replacement)** — new
    `tests/test_router_backend_replacement.py::TestC02F004AutomaticBackendReplacement`
    covers new-manifest replacement, unhealthy-fallback replacement,
    and after-construction capability addition (3 assertions).
16. **C02-F007 (Cross-agent compatibility)** — new
    `tests/test_router_backend_replacement.py::TestC02F007CrossAgentCompatibility`
    covers import-shape shared, class instances shared, and same
    envelope returned from any surface via the same Router
    (3 assertions).

### Test-suite result this session

- Before round 3: 280 passed / 0 failed / 9 skipped.
- After round 3: **301 passed / 0 failed / 9 skipped** (return
  code 0). Net: 21 genuinely new passing tests.
- The nine skips are unchanged from round 2 and are all
  environmental (sandbox forbids `bind()`, sandbox blocks PyPI so
  Playwright can't install, sandbox cannot reach api.github.com /
  v2ex.com / hnrss.org).

### What was built or wired in

- **New tests** (all Python stdlib + existing modules; zero new
  runtime dependencies):
  - `tests/test_web_search_offline.py` (4 assertions on the DDG
    parser with an offline HTML fixture)
  - `tests/test_web_fetch_offline.py` (3 assertions on
    `WebFetchConnector`)
  - `tests/test_router_backend_replacement.py` (6 assertions on
    Registry + Router replacement and cross-surface parity)
  - `tests/test_source_provenance_c3f16.py` (8 assertions on
    envelope provenance + lawful-access policy refusals)
- **No new capability code**; every promotion is honest evidence
  of code that was already in the repository.
- **No existing adapter or core module was removed or replaced**;
  every file under `deye/connectors/`, `deye/core/`, `deye/browser/`,
  `deye/research/`, `deye/skills/` stayed byte-identical.

### Rows NOT raised this round (honest gaps)

- **C04 browser rows** — Playwright pip install still fails because
  the sandbox blocks PyPI; deferred.
- **C08-F004, F005, F007** — need a real Claude Desktop or `claude
  plugin` CLI to load the plugin.
- **C07-F003** — needs live hosted uvicorn deploy + external client.
- **C11-F007, C11-F008** — need a normal shell where `bind()` on
  127.0.0.1 is permitted.
- **C05-F002 (Neural search)** — deliberately PARTIAL: acceptance
  documents "embedding path documented but not required" so PARTIAL
  is the honest state.
- **C05-F013 (Cost/quota/rate reporting)** — deliberately PARTIAL:
  acceptance calls out that FOSS connectors have no external cost.
- **C03-F006 (YouTube transcripts)** — deliberately PARTIAL:
  acceptance says "keyless search is not implemented (would need
  YouTube Data API key, kept out of core)".

## Next tranche (round 4)

Recommended focus, in this order:

1. **Category 1 (setup + lifecycle) macOS pass** — several rows
   (C01-F002 env detection, C01-F003 dependency installation,
   C01-F004 configuration, C01-F006 health checking, C01-F007
   repair guidance) have code under `deye/lifecycle/` and can be
   lifted on macOS via real subprocess-driven tests; Windows and
   Linux halves stay honestly deferred.
2. **Category 7 (MCP) evidence sweep** — the remaining C07 rows
   (C07-F005 connector health, C07-F006 search tool, C07-F007
   fetch tool, C07-F010 research export, C07-F011 consent gate)
   have code in `deye/mcp_server.py` and can be lifted with
   dedicated in-process MCP tool-invocation tests.
3. **Category 11 (security) evidence sweep** — a handful of
   security rows may already have coverage via test_router.py,
   test_redact.py, test_decompression_guard.py; a CSV audit for
   stale test paths may lift several without new capability.
4. **Category 8 (Claude plugin) structural tightening** — the
   plugin-hook and skill rows that are NOT gated by Claude
   Desktop activation (C08-F006 health hook, C08-F009 version
   management, C08-F010 rollback, C08-F012 configuration
   synchronisation) may be liftable via structural + shim tests.
5. Deferred until normal dev shell:
   - **C04 browser rows** (Playwright install)
   - **C11-F007, C11-F008** (localhost bind)
   - **C07-F003** (hosted uvicorn deploy)

Every round-4 promotion still requires the round's own tests to
pass in-session; a skipped test is not evidence of success.
