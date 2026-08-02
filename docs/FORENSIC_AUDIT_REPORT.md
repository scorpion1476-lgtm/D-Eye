# D-Eye — design-provenance attribution record

> **Type:** design-provenance / attribution record. This file exists to
> preserve the honest record of which external projects informed D-Eye's
> design and to satisfy each project's licence attribution obligations.
> It is NOT product documentation. External project names here are
> intentional attribution (permitted under the docs policy in the same
> way `THIRD_PARTY_NOTICES.md` is permitted); D-Eye's user-facing docs
> (README, guides, CLI/plugin descriptions) use neutral D-Eye terminology
> only.
>
> _Independent re-audit produced 2026-07-27; retained verbatim as a
> historical attribution record._

## 1. Source & licence reconciliation

All four "code" attachments are the SAME upstream project, **Agent-Reach**
(MIT, "Agent Eyes" / "Neo Reid", https://github.com/Panniantong/Agent-Reach):

| Attachment | Identity | Role |
|---|---|---|
| `Agent-Reach-main.zip` | Agent-Reach v1.5.0 (newest; has `url.py`, facebook, instagram, mcporter, `_opencli_site`) | primary reference |
| `v1.5.0 ... OpenCLI ... .tar.gz` | Agent-Reach @ commit `f65526c` (older sibling; those files absent) | version-diff |
| `agent-reach-1.0.0.tar.gz` | Agent-Reach skill/reference bundle only | skill behaviour |
| `mcpmarket-plugin-me-claude.zip` | Third-party MCPmarket Claude plugin (MIT) | plugin/supply-chain analysis |
| `Agent-Reach_Exa_FOSS_...Report.md` | The design brief | architecture source |

D-Eye is an independent clean re-implementation: **no upstream source file is
vendored**. The one pattern reused (a host-allowlist helper) was re-written and
hardened into `deye/core/policy.py`. Attribution is in `NOTICE`; obligations are
in `docs/LICENSE_INVENTORY.md`. D-Eye core has **zero third-party runtime deps**.

## 2. Credential / secret audit
- The MCPmarket plugin's `.mcp.json` contained a live-looking bearer token
  (`sk_user_...`). **Treated as compromised. Not reproduced anywhere in D-Eye.**
  Owner must revoke/rotate it.
- D-Eye's own repo: a repo-wide secret-scan test asserts no live-token-shaped
  strings exist outside test fixtures. Verified passing.
- The D-Eye plugin ships NO token, NO remote skill-sync, NO telemetry (all three
  present in the reference plugin were deliberately excluded).

## 3. Defects found in 0.1.0 and corrected in 0.2.0

| # | Finding in 0.1.0 | Correction (verified) |
|---|---|---|
| D1 | `query_evidence` was a misleading stub returning a note | Real SQLite evidence store; persistence verified cross-process |
| D2 | Docker ran stdio, but docs implied Claude web could use it | Real Streamable-HTTP remote service with enforced bearer auth; Docker relabelled; matrix corrected |
| D3 | SSRF resolved DNS then let urllib re-resolve (TOCTOU/rebinding gap) | Connection-level IP pinning; SNI/cert still validated; live-tested |
| D4 | No decompression-bomb protection | gzip/deflate decompressed-size cap added + tested |
| D5 | Plugin `.mcp.json` used `python` + `${DEYE_HOME:-~/.deye}` JSON shell-expansion (unsupported) | `python3 -m deye.mcp_server`; expansion removed; pip-first documented |
| D6 | Optional hosted-search adapter status ambiguous | Adapter removed; keyless FOSS search is the sole default |
| D7 | Compat matrix could be read as "hook = global activation" | Corrected: hook is a local health check; local stdio unreachable from web |

## 4. Validation performed
See `docs/TEST_REPORT.md` for the actually-executed results (Python 3.12.3,
pytest, 45 tests passing, live SSRF/remote/evidence checks). Items not verifiable
here (Docker build, live Claude-web handshake, non-Linux paths) are labelled as
such rather than claimed.

## 5. Residual risks / roadmap
Connector sandboxing, signed skill/plugin bundles, SBOM+SAST in CI, evidence
*graph* with contradiction detection, browser edge, multi-tenant isolation. See
`docs/THREAT_MODEL.md`.
