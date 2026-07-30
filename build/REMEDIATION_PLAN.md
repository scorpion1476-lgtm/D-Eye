# D-Eye Remediation Plan

Living plan for closing the 112 below-PRODUCTION-READY rows to feature
parity with the 12-category reference sources under a FOSS-only,
local-first mandate. Updated each round. See `PROGRESS.md` for the
round-by-round record of what was actually completed with evidence.

## Baseline (session 10 audit)

| Status | Count |
|---|---|
| PRODUCTION READY | 55 |
| IMPLEMENTED BUT NOT FULLY VERIFIED | 92 |
| PARTIAL | 12 |
| BLOCKED BY EXTERNAL PLATFORM | 8 |
| **TOTAL** | **167** |

The gap to parity is 112 rows. Most are held back not by missing
code but by missing end-to-end evidence, which is closeable locally
with free and open-source tooling in most cases.

## Gap taxonomy

Each below-PROD row falls into one of these buckets:

1. **CSV-artifact only.** The row is functionally complete but the
   traceability CSV points at a stale path (e.g., a file was
   reorganized). Fix the CSV path. Zero code change.
   - C08-F003, C12-F017 (stale `plugin/d-eye/skills/deye/SKILL.md`
     path; the skill was reorganized into 8 specialised subdirs each
     with its own SKILL.md).

2. **Real local end-to-end test missing.** The unit tests exist but
   no round-trip through the full stack has been demonstrated. Add
   real E2E test(s) using stdlib http.server or Starlette TestClient.
   - Redirect re-evaluation (C11-F007), IP pinning (C11-F008),
     private-IP block through the full fetch stack (C11-F004).
   - Remote HTTP MCP end-to-end via Starlette TestClient
     (C07-F003, C11-F011, C12-F004).
   - Local stdio MCP end-to-end via subprocess JSON-RPC
     (C12-F002; test already exists but the audit's live-gated set
     needs to reflect that).

3. **Live-browser gated.** The row requires a real Playwright browser
   run. Closeable locally by installing Playwright + a chromium
   binary as a test-time extra (never a core dependency).
   - C04-F001, C04-F003, C04-F005, C04-F006, C04-F007, C04-F008,
     C04-F009.

4. **Live Claude Desktop / Web / Cowork surface gated.** The row
   requires the actual Claude Desktop or Claude Web to load the
   plugin. Cannot be closed inside this sandbox because Claude
   Desktop is a proprietary surface. Stays BLOCKED BY EXTERNAL
   PLATFORM or IMPLEMENTED BUT NOT FULLY VERIFIED with a one-line
   note of exactly what live run would settle it.
   - C08-F004, C08-F005, C08-F007, C08-F008, C08-F011.

5. **Cross-platform gated.** The row requires a Windows or Linux
   runner. Closeable locally on macOS only for the macOS half;
   Windows/Linux rows stay IMPLEMENTED BUT NOT FULLY VERIFIED with
   the exact matrix run that would settle them.
   - C01-F001, C01-F002, C01-F003, C01-F005, C01-F006, C01-F008.

6. **Legally-blocked social platform.** Row is BLOCKED BY EXTERNAL
   PLATFORM by design (Twitter API deprecation, LinkedIn ToS, etc.).
   Nothing to do at the code layer; verify the honest blocker note.
   - C03-F004, C03-F008, C03-F009, C03-F010, C03-F011.

7. **Missing implementation.** The row genuinely lacks code. Build
   the capability on top of existing modules and connectors.
   - (small residual after rounds 1-2; identified per-round from the
     audit's E1 fails.)

## Round-by-round strategy

- **Round 1** (this round): buckets 1, 2. High-confidence, deterministic,
  closeable with stdlib + already-installed FOSS packages.
- **Round 2**: bucket 3 (Playwright headless), and any straightforward
  bucket-2 rows not reached in round 1.
- **Round 3**: bucket 7 (build residual code); revisit bucket 5 on
  macOS for the macOS half.
- **Round 4 and later**: bucket 4 stays honestly labelled with the
  exact live run that would settle it; the same for the Windows and
  Linux halves of bucket 5, until a matrix runner is available.

## Approach for the ACHIEVED_LOCAL_E2E override

Session 9's audit set rows as live-gated based on the general shape
of their acceptance. When a round adds a genuine local end-to-end
harness that exercises the row through the full stack, session 10's
audit adds the row to `ACHIEVED_LOCAL_E2E` and subtracts it from
the live-gated buckets. A row is added to `ACHIEVED_LOCAL_E2E` only
if the specific evidence exists in the repository and the tests
actually pass in the audit session (session 10 runs pytest as part
of its evidence collection).

## Guardrail cross-reference

- Reused, not replaced, existing adapters: `deye/connectors/*`,
  `deye/core/*`, `deye/mcp_server.py`, `deye/remote.py`,
  `deye/browser/*`, `deye/research/*`.
- FOSS-only mandate preserved: no core path added a paid or
  credentialed dependency; every new test uses stdlib
  (`http.server`, `socket`, `ssl`) or already-installed FOSS
  (`starlette` TestClient, the `mcp` optional extra which is
  Apache-2.0).
- No CSV row deleted or merged. Stale paths are corrected in place.
