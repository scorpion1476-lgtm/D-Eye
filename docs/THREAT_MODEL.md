# D-Eye threat model (summary)

Derived from section 11 of the forensic report and mapped to what this
repository implements today vs. what remains roadmap.

## Assets
User credentials/cookies, local filesystem, the model's instruction context,
tenant/project data, and the integrity of retrieved evidence.

## Primary threats -> controls

| Threat | Control in this repo | Status |
|---|---|---|
| SSRF / metadata pivot | `core/policy.py` + `connectors/base.py`: scheme allowlist, userinfo rejection, DNS resolution + private/loopback/link-local/metadata IP blocking, per-redirect re-validation, IPv4-mapped-IPv6 unwrapping, **connection-level IP pinning** | Implemented + tested |
| DNS rebinding / TOCTOU | Host resolved+checked ONCE, then the TCP connection is PINNED to that vetted IP (SNI/cert still validated against the real host). Closes the check-vs-connect window. | Implemented + live-tested |
| Decompression bomb (gzip/deflate) | Raw size cap + decompressed size cap in `connectors/base.py` | Implemented + tested |
| Misleading capability (`query_evidence`) | Now backed by a real SQLite evidence store (`core/evidence.py`); persistence verified cross-process | Implemented + tested |
| Credential leakage to logs/model | `core/redact.py` applied on all CLI/MCP output; secrets stored as references only (`env:` / `keychain:`) | Implemented + tested |
| Leaked token in bundled config | Plugin `.mcp.json` uses a local stdio server, no token; repo-wide secret scan test | Implemented + tested |
| Remote skill supply-chain | Plugin has **no** SessionStart remote-sync; hook is a local health check only | Removed by design |
| Telemetry exfiltration | Plugin ships **no** PostToolUse telemetry hook | Removed by design |
| Prompt injection from content | All envelopes carry `trust.untrusted=True`; skill instructs the model never to obey fetched text | Implemented (labelling) |
| State-changing actions | Read-only default; `ConsentPolicy` blocks write/browser actions unless explicitly granted | Implemented + tested |
| Resource exhaustion / runaway crawl | `Limits`: timeout, max bytes, redirect + crawl depth, concurrency ceilings | Implemented |
| Backend compromise / flapping | Router circuit breaker + health probe + safe fallback | Implemented + tested |

## Explicitly roadmap (NOT yet implemented; do not assume)
- Evidence *graph* with contradiction detection (a persistent evidence STORE with source-change detection is now implemented; the richer graph is still roadmap).
- Connector sandboxing in a separate low-privilege process / container.
- Signed plugin/skill bundles with hash pinning and rollback registry.
- SBOM generation, SAST, dependency + container scanning in CI.
- Browser edge (Playwright / OpenCLI), transcription, tenant isolation at DB level.

Security is a process: this slice reduces the highest-severity risks first and
names the rest honestly rather than implying completeness.
