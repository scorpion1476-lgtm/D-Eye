# D-Eye - Production Readiness Report (historical)

> **Historical record.** This is a Phase A and Phase B snapshot from
> 2026-07-28 to 2026-07-29. The branches it names
> (`feature/phase-a-foundation`, `feature/phase-b-hardening`) have since
> been consolidated into the current line, and its test counts are
> superseded.
>
> For current, authoritative status see the "Status, honestly" section of
> the top-level [`README.md`](../README.md). The latest verified run is 358
> passed, 0 failed out of 363 collected, and under the strict evidence
> rubric 55 of 167 catalogue rows are PRODUCTION READY. The Phase-A section below is a
> pre-integration record; its per-item states and "recommended next
> actions" no longer reflect the current tree.

**Date:** 2026-07-28 · **Baseline:** v0.2.0-validated · **Branch:** feature/phase-a-foundation

## Scope of this report
This covers Phase A of the production-gap programme: evidence graph + contradiction detection, GitHub research connector, and the SBOM/SAST/dependency/secret-scan CI foundation. It records only what was executed and verified in this session.

## What changed and its verified state

| Feature | Status | Evidence |
|---|---|---|
| Evidence graph + contradiction detection | IMPLEMENTED BUT NOT FULLY VERIFIED | 5 unit tests pass; polarity + numeric heuristics; precision/recall on real corpora not measured |
| GitHub research connector (read-only) | IMPLEMENTED BUT NOT FULLY VERIFIED | 4 unit tests pass; live call to `api.github.com` succeeded through the SSRF-guarded path; rate-limit handled gracefully |
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
