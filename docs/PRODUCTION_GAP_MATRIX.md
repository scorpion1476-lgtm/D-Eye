# D-Eye - Production Gap Matrix (superseded, historical only)

> **SUPERSEDED.** This file is a historical snapshot from 2026-07-29 to
> 2026-07-30, retained only as a record. Do not treat any status or number
> below as current.
>
> The current, authoritative status is the "Status, honestly" section of
> the top-level [`README.md`](../README.md). Under the strict evidence
> rubric, 55 of 167 catalogue rows are PRODUCTION READY; the remainder are
> IMPLEMENTED BUT NOT FULLY VERIFIED, PARTIAL, or BLOCKED BY EXTERNAL
> PLATFORM. An earlier local pass that reached 146 PRODUCTION READY, and
> the 63 provisional figure once cited here, were both corrected downward
> to the strict rubric of 55.
>
> The per-row assessments below reflect state on 2026-07-29 and are stale
> (the browser adapter, multi-tenant scoping, licence-drift enforcement,
> MCP tool invocation, live OSV audit, and the specialised D-Eye skills
> have all shipped since). This file also references external product
> names that D-Eye's documentation policy now keeps in
> `THIRD_PARTY_NOTICES.md` only.

**Baseline:** v0.2.0-validated · **Working branch:** feature/phase-a-foundation
**Last updated:** 2026-07-28 (Phase A: evidence graph, GitHub connector, security CI)
**Method:** source inspection + real test execution + live GitHub read. No status is taken from the README on trust.

Statuses (exact wording): PRODUCTION READY · IMPLEMENTED BUT NOT FULLY VERIFIED · PARTIAL · NOT IMPLEMENTED · BLOCKED BY EXTERNAL PLATFORM · NOT APPLICABLE.

`PRODUCTION READY` requires implementation + integration tests + security tests + docs + rollback behaviour, all passing, exercised in a real supported environment.

## Verified test results (this session)

| Environment | Result | How |
|---|---|---|
| Core (no optional deps) | **69 passed, 1 skipped** | `python -m pytest -q -rs` (Phase B; was 62/1 at Phase A) |
| With MCP extras (clean venv) | **73 passed, 0 skipped** | `pip install ".[remote]"` (mcp<2); was 66 at Phase A |
| Skipped in core run | `test_remote_auth.py` - needs optional `mcp` | pytest `-rs` |
| SAST (bandit) | **0 issues** across all severities | `bandit -r deye` |
| Live GitHub connector | reached `api.github.com` via SSRF-guarded path; rate-limit handled | `deye repo psf/requests` |

The "51 passed" figure from earlier releases is **not** this session's result and is not claimed as such.

## Environment reality (this session)

Claude chat + a Linux sandbox + a live GitHub connector. **Not** a shell on your Mac and **not** Claude Desktop.
- Available: run Python/tests/build files; read+write your GitHub repo (authenticated `scorpion1476-lgtm`).
- Not available here: `gh` CLI, Docker, Playwright; Desktop Commander on your real machine; configuring your Claude Desktop; OS package installs; cloud connector registration.

---

## Category status

### 1. Automatic installation & setup - PARTIAL
`scripts/install.sh` + `deye setup` + `init-claude` (backup+merge) exist and the Linux path is exercised. macOS/Windows installers, idempotent repair/rollback/uninstall/update, and a non-technical health report are **NOT IMPLEMENTED**. macOS/Windows are **BLOCKED BY EXTERNAL PLATFORM** for verification from here.

### 2. Intelligent capability routing - IMPLEMENTED BUT NOT FULLY VERIFIED
Registry, preference-ordered router, health-based fallback, **circuit breaker** and per-connector audit exist and are unit-tested (`test_router.py`). Retry/timeout tuning and update detection are **PARTIAL / NOT IMPLEMENTED**.

### 3. Internet & content connectors - PARTIAL
Live & tested: web search (keyless DuckDuckGo), web fetch+extract, RSS/Atom (now with an XXE/entity guard), **GitHub repo inspection (new)**. Provenance + read-only default enforced. YouTube, Reddit, X, LinkedIn/FB/IG, Bilibili, Xiaohongshu, V2EX, Xueqiu, Xiaoyuzhou → **NOT IMPLEMENTED**.

### 4. Browser automation - NOT IMPLEMENTED (at time of writing)
Optional local browser adapter, profiles, isolated contexts, a11y-tree, screenshots, consent clicks - not present at time of writing. (An opt-in browser adapter has since shipped as `deye/browser/` behind the `[browser]` extras group; see the current status report.)

### 5. Semantic research - IMPLEMENTED BUT NOT FULLY VERIFIED
An optional third-party search-provider adapter existed at the time this doc was written: authenticated POST via the SSRF-guarded path; search + contents + highlights; domain include/exclude; date filters; find-similar; answer; cost reporting; keyless fallback. Unit-tested with mocked HTTP; keyless fallback verified. Not verified against the live provider API (no key in this environment). Research-task polling → **NOT IMPLEMENTED** at time of writing.

### 6. Evidence & research quality - IMPLEMENTED BUT NOT FULLY VERIFIED
Persistent SQLite evidence, provenance, hashes, cited Markdown/JSON export, change detection, dedup (pre-existing, tested). **New:** evidence graph (entities + claims) and **contradiction detection** (polarity + numeric heuristics with confidence scores), unit-tested. Heuristic precision/recall on real corpora is **not measured**; confidence/source-quality scoring beyond this is **PARTIAL**.

### 7. MCP architecture - IMPLEMENTED BUT NOT FULLY VERIFIED
Local stdio MCP facade and remote Streamable-HTTP with bearer auth exist. Remote-auth test passes **only with optional extras installed** (skipped in the core run - reported separately above). Rate limiting, request-size limits, tenant context, sessions, Docker-verified deploy, HTTPS/reverse-proxy proof → **PARTIAL / NOT IMPLEMENTED / BLOCKED BY EXTERNAL PLATFORM** (Docker not available here).

### 8. Claude plugin, skills & hooks - IMPLEMENTED BUT NOT FULLY VERIFIED
Plugin manifest, marketplace.json, `.mcp.json`, SKILL.md, health-check hook present and `test_init_claude.py` passes. Not exercised inside a real Claude Desktop from here. MCPB/Desktop-Extension packaging, update/rollback, version detection → **NOT IMPLEMENTED**. A local hook **cannot** globally activate a cloud Claude surface - documented, not claimed.

### 9. GitHub & developer workflow - IMPLEMENTED BUT NOT FULLY VERIFIED
Private repo + `v0.2.0-validated` release verified live. **New:** CI workflow (tests × {core, mcp} matrix + lint + SBOM) and a **Security workflow** (bandit SAST, secret scan, pip-audit, dependency-review, SBOM artifact) with least-privilege `contents: read`. Workflows are committed but **a green Actions run has not yet been observed** from this session, so not marked PRODUCTION READY. Signed tags/releases, checksums → **NOT IMPLEMENTED**.

### 10. Provider-neutral backend (FOSS) - NOT IMPLEMENTED (at time of writing)
Only bearer auth on the remote MCP exists at time of writing. Identity, tenant, object storage, jobs, RBAC, audit log → not present. (A local `deye/backend/` package has since shipped with local auth (scrypt), SQLite queue, filesystem SHA-addressable object store, RBAC, JSON observability, Prometheus text emitter, event bus, and per-tenant lifecycle - see the current status report.)

### 11. Security & software supply chain - IMPLEMENTED BUT NOT FULLY VERIFIED
Real & tested: SSRF with connection-level IP pinning, private/metadata-IP blocking, decompression caps, credential redaction, in-repo secret test, **new XXE/entity guard** on feeds. **New:** SBOM generator (declared + installed modes), bandit SAST (0 findings), pip-audit + dependency-review + secret-scan CI. Signed tags/releases, provenance attestations, reproducible builds, container scanning, connector sandboxing → **NOT IMPLEMENTED**.

### 12. Universal lifecycle / cross-surface activation - PARTIAL / BLOCKED BY EXTERNAL PLATFORM
Local CLI + local stdio MCP + remote HTTP MCP + config helpers exist (PARTIAL). Verified activation inside Claude Desktop/Code/web/Projects/Cowork and cloud connector registration are **BLOCKED BY EXTERNAL PLATFORM** from this session (needs the real client; no supported registration API).

---

## Automatable from here vs blocked

**Done here (built + tested, pushed to GitHub):** evidence graph + contradiction detection, GitHub research connector, keyless FOSS web search, XXE guard, SBOM generator, bandit-clean SAST, CI + Security workflows, updated docs.

**BLOCKED BY EXTERNAL PLATFORM (needs your machine / hosting / Claude client):** macOS/Windows installer proof, Desktop-Commander automation, Docker deploy proof, live Claude Desktop/web/Projects/Cowork activation, and remote connector registration.
