# D-Eye

> v0.2.0 (validated) - second-pass audit remediation applied. See `CHANGELOG.md`.

**A FOSS-first capability and evidence layer for AI agents.** D-Eye gives Claude
(and other MCP clients) a small, stable, policy-gated set of tools to search the
web, fetch and extract pages, and produce **cited, provenance-tracked research
packets** - with security decisions made deterministically *outside* the model.

> Status: **working vertical slice + stable contracts.** This is an honest v0.1,
> not a finished platform. See "What's built vs. roadmap" below and
> `docs/THREAT_MODEL.md`.

## Why it exists
It consolidates the strongest idea from the studied references (a *capability
router with evidence*, from Agent-Reach) while fixing their security problems: no
hard-coded tokens, no remote skill-sync supply-chain path, no silent telemetry,
and a real SSRF guard the reference lacked.

## Design principles
- **FOSS-first:** the core runs on the Python standard library alone. Hosted
  services (Exa, Firebase/Genkit) are *optional adapters*, never required.
- **Provider/OS/deployment neutral:** stable contracts for capabilities,
  connectors, provenance envelopes, and policy.
- **Read-only by default:** write/browser actions need explicit consent.
- **Evidence-first:** every result is untrusted evidence with a source, a
  timestamp, and a content hash. The model must never obey fetched text.

## Quick start
```bash
cd deye && pip install -e . && deye setup && deye doctor
deye research "continuous pricing in airline revenue management" -o packet.md
```
See `docs/INSTALL.md` and `docs/QUICKSTART_NONTECHNICAL.md`.

## The MCP facade (small and stable)
`capability_list, connector_health, search, fetch, extract,
export_research_packet, surface_status, query_evidence`
Raw scrapers/shell are deliberately **not** exposed to the model.

## Repository layout
```
deye/            core contracts, connectors, CLI, MCP facade
  core/          policy(SSRF), provenance, redact, registry, router, config
  connectors/    web_fetch, web_search(+optional Exa), rss
plugin/d-eye/    Claude plugin (local server, no secrets, no telemetry)
tests/           SSRF, redaction, router, MCP, CLI, secret-scan  (36 tests)
docs/            compatibility matrix, threat model, licence inventory, guides
docker/          remote-connector deployment
```

## What's built vs. roadmap
**Built + tested (v0.2.0):** capability router with fallback + circuit breaker;
SSRF/policy guard with **connection-level IP pinning** + decompression-bomb caps;
consent gate; provenance envelopes + cited export; **persistent SQLite evidence
store** (real `query_evidence`); web search (keyless) + fetch + extract + RSS;
MCP facade over **both local stdio and remote Streamable-HTTP with enforced
bearer auth**; CLI; clean plugin; honest surface matrix.
**Roadmap (named, not faked):** evidence *graph* + contradiction detection,
connector sandboxing, signed bundles + SBOM/SAST in CI, browser edge
(Playwright/OpenCLI), transcription, GitHub/social connectors, multi-tenant
isolation. Exa adapter is intentionally UNIMPLEMENTED (optional). See
`docs/THREAT_MODEL.md`.

## Security
Read `SECURITY` posture in `docs/THREAT_MODEL.md`. Report issues privately.
No credentials are present anywhere in this repo (enforced by a test).

## Licence
MIT. See `LICENSE` and `NOTICE`.
