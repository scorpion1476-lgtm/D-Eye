# D-Eye - Production Readiness Report

> **Current state (2026-07-29):** This branch (`feature/phase-b-hardening`, PR #1 into `main`) carries the combined Phase A + Phase B tree. Validated: core **69 passed / 1 skipped**, with MCP extras **73 passed / 0 skipped**, bandit 0, pip-audit 0, SBOM generated. CI was observed on the push and PR; tests/bandit/secret-scan/pip-audit/SBOM pass. The `dependency-review` check is red only because GitHub Code Security / Advanced Security (GHAS) is unavailable in this private-repo plan - **BLOCKED BY EXTERNAL PLATFORM** (dependency-CVE coverage is provided by the passing pip-audit job; the Node 20 deprecation notice is advisory only).
>
> The Phase-A section below is retained as a **historical pre-integration record - superseded on 2026-07-29**; its "no green Actions run observed" and "recommended next actions" no longer reflect the current state.

**Date:** 2026-07-28 · **Baseline:** v0.2.0-validated · **Branch:** feature/phase-a-foundation

## Scope of this report
This covers Phase A of the production-gap programme: evidence graph + contradiction detection, GitHub research connector, real Exa adapter, and the SBOM/SAST/dependency/secret-scan CI foundation. It records only what was executed and verified in this session.

## What changed and its verified state

| Feature | Status | Evidence |
|---|---|---|
| Evidence graph + contradiction detection | IMPLEMENTED BUT NOT FULLY VERIFIED | 5 unit tests pass; polarity + numeric heuristics; precision/recall on real corpora not measured |
| GitHub research connector (read-only) | IMPLEMENTED BUT NOT FULLY VERIFIED | 4 unit tests pass; live call to `api.github.com` succeeded through the SSRF-guarded path; rate-limit handled gracefully |
| Exa adapter (auth POST, contents, filters, cost, fallback) | IMPLEMENTED BUT NOT FULLY VERIFIED | 4 unit tests pass incl. keyless fallback; not run against the live Exa API (no key here) |
| XXE / entity guard on RSS/Atom | PRODUCTION READY (module-level) | DOCTYPE rejection test + normal-feed test pass; bandit MEDIUM cleared |
| SBOM generator | IMPLEMENTED BUT NOT FULLY VERIFIED | runs; emits CycloneDX 1.5 JSON (declared + installed modes) |
| Bandit SAST | PASS | 0 issues across all severities |
| CI + Security workflows | IMPLEMENTED BUT NOT FULLY VERIFIED | valid YAML, least-privilege perms; **no green Actions run observed yet** from this session |

Nothing above is marked `PRODUCTION READY` at the platform level, because the strict bar (integration + security + docs + rollback, exercised in a real supported environment) is not yet met end-to-end for these features. The XXE guard is the one component whose full behaviour is proven in isolation.

## Blocked by external platform (unavoidable from this session)
- macOS / Windows installer validation, Desktop-Commander machine automation, Docker deploy proof.
- Live activation inside Claude Desktop, Claude web, Projects, or Cowork.
- Remote connector registration and tool handshake (no supported automation API).

## Recommended next actions
1. Let the pushed CI + Security workflows run once on GitHub Actions and confirm a green result; then this section can move those items forward.
2. On your Mac (with Desktop Commander), run `scripts/install.sh` and `deye init-claude` to validate local installation and Claude Desktop registration.
3. Provide an `EXA_API_KEY` (as an environment reference, never inline) if you want the Exa adapter verified against the live API.
