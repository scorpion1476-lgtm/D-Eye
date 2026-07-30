<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/branding/D-Eye_Icon1.svg" width="180">
    <source media="(prefers-color-scheme: light)" srcset="assets/branding/D-Eye_Icon21.svg" width="180">
    <img alt="D-Eye" src="assets/branding/D-Eye_Icon21.svg" width="180" height="32">
  </picture>
</p>

# D-Eye

**A FOSS-first, local-first capability and evidence layer for AI agents.**

D-Eye gives AI clients (Claude Desktop, Claude Code, and any MCP-compatible
tool) a small, stable, policy-gated set of capabilities to search the public
web, fetch and extract pages, produce cited research packets, and inspect
a persistent evidence store. Security decisions run deterministically
**outside the model**; retrieved content is treated as **untrusted evidence**,
never as instructions.

> **Verified in this environment (2026-07-30).** 239 tests pass, 8 skipped
> (live-network tests that need direct DNS the sandbox does not provide;
> the same tests are written to run and pass on any normal developer host).
> Bandit static analysis: 0 HIGH / 0 MEDIUM / 8 LOW (informational
> subprocess-usage flags). Live pip-audit against OSV.dev: no known
> vulnerabilities across 86 installed packages. 63 of 167 catalogue rows
> are PRODUCTION READY with executed acceptance evidence; the remaining
> rows carry precise environmental-blocker reasons in
> `reports/REMAINING_EXTERNAL_BLOCKERS.md`. D-Eye is **not** claimed as
> "production ready overall" or "100 percent complete".

---

## Contents

- [Who it is for](#who-it-is-for)
- [What it solves](#what-it-solves)
- [Five-minute quick start](#five-minute-quick-start)
- [Architecture at a glance](#architecture-at-a-glance)
- [Capabilities](#capabilities)
- [Skills](#skills)
- [Connectors](#connectors)
- [Security model](#security-model)
- [Offline mode](#offline-mode)
- [Configuration](#configuration)
- [Local and remote MCP](#local-and-remote-mcp)
- [Practical workflows](#practical-workflows)
- [Troubleshooting](#troubleshooting)
- [Developer guide](#developer-guide)
- [Validation status](#validation-status)
- [Compatibility](#compatibility)
- [Current limitations](#current-limitations)
- [Licence and attribution](#licence-and-attribution)
- [Roadmap](#roadmap)

## Who it is for

- **Research analysts** who need answers with citations that survive an
  audit trail (source URL, retrieval timestamp, content hash).
- **Security-conscious teams** who want a hardened fetch path (SSRF
  gate, IP pinning, decompression bomb guard, redirect re-validation)
  and never want an LLM to obey untrusted text.
- **MCP tool builders** who need a stable, small tool surface they can
  extend without rewriting the security stack.
- **Offline and air-gapped users** who want research over a local
  evidence store with zero required network egress.

## What it solves

**The practical problem.** Off-the-shelf LLM stacks give confident
answers without provenance. When the answer is wrong, or when a
reviewer asks "where did this come from?", there is nothing to check.
D-Eye captures a source, a timestamp, a content hash, and a retrieval
context for every piece of evidence, and hands the client a fully cited
research packet instead of a black-box response.

**The technical problem.** Retrieved web content routinely tries to
manipulate the LLM ("ignore previous instructions ..."). D-Eye handles
that in three places at once:

1. Every fetched artefact is tagged `trust.untrusted=True`; the client's
   skill instructions tell the model never to follow instructions found
   inside untrusted evidence.
2. The fetch path is SSRF-hardened before it ever reaches the network:
   scheme allowlist, URL userinfo rejection, DNS-resolve-then-pin to
   the validated IP (fixes the classic DNS-rebinding TOCTOU),
   private-IP and cloud-metadata-IP block, decompression bomb guard,
   response size cap, redirect re-validation at every hop.
3. Every audit-log entry, every log line, every exported packet passes
   through a credential redactor before it is written or emitted.

## Five-minute quick start

Prerequisites: **Python 3.10 or newer**. That is the entire
prerequisite list. The core install pulls **zero runtime dependencies**
(Python standard library only).

```bash
# 1. install core (FOSS, no keys, no accounts)
git clone https://github.com/scorpion1476-lgtm/D-Eye D-Eye
cd D-Eye/repository/deye
python3 -m venv .venv
./.venv/bin/python -m pip install -e .

# 2. one-time setup (writes ~/.deye/config.json with FOSS defaults)
./.venv/bin/deye setup
./.venv/bin/deye doctor          # confirm connectors healthy

# 3. do some research (search, fetch, cite, persist)
./.venv/bin/deye research "continuous pricing airline revenue management" \
    -o packet.md

# 4. query what was captured
./.venv/bin/deye evidence "continuous pricing"
```

Full quickstart, including offline mode and Claude Desktop or Claude
Code registration, is in [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

## Architecture at a glance

```mermaid
%%{init: {'theme':'base'}}%%
flowchart LR
  CLI[CLI]:::client -->|capability request| ROUTER
  MCP[MCP client<br/>Claude Desktop / Code]:::client -->|MCP tool call| ROUTER

  subgraph CORE [D-Eye core - stdlib only]
    ROUTER[Capability router<br/>fallback, circuit breaker,<br/>audit + consent]:::core
    POLICY[Policy engine<br/>SSRF, IP pinning,<br/>redirect re-eval, limits]:::core
    REDACT[Redactor<br/>headers + patterns]:::core
    EVIDENCE[Evidence store<br/>SQLite, multi-tenant]:::core
    RESEARCH[Research<br/>FTS5, extractive answer,<br/>dedup, quality]:::core
    PROV[Provenance<br/>Envelope, hashes, trust]:::core
  end

  subgraph CONN [Connectors - keyless FOSS]
    C1[web_search<br/>web_fetch<br/>rss<br/>github_repo]:::conn
    C2[reddit, v2ex<br/>youtube, xueqiu<br/>xiaoyuzhou]:::conn
    C3[platform-boundary<br/>stubs]:::stub
  end

  subgraph OPT [Optional adapters]
    BROWSER[Browser adapter<br/>opt-in]:::opt
    BACKEND[Local backend<br/>auth, queue, storage,<br/>RBAC, observability]:::opt
    EMBED[Local embeddings<br/>planned]:::plan
  end

  ROUTER --> POLICY
  ROUTER --> REDACT
  ROUTER --> EVIDENCE
  ROUTER --> RESEARCH
  ROUTER --> PROV
  ROUTER --> C1
  ROUTER --> C2
  ROUTER --> C3
  ROUTER -.->|opt-in| BROWSER
  ROUTER -.->|opt-in| BACKEND
  RESEARCH -.->|planned| EMBED

  classDef client fill:#e6f0ff,stroke:#3355aa,color:#111
  classDef core fill:#e8f6ea,stroke:#2c7a3f,color:#111
  classDef conn fill:#fff6dd,stroke:#a07020,color:#111
  classDef stub fill:#fff0f0,stroke:#a03030,color:#111
  classDef opt fill:#efe6ff,stroke:#5f3fa0,color:#111
  classDef plan fill:#f3f3f3,stroke:#666,color:#333,stroke-dasharray: 4 3
```

If the Mermaid diagram does not render in your Markdown viewer, an
equivalent walkthrough is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Capabilities

| # | Category | What D-Eye ships today |
|---|---|---|
| 1 | Setup and lifecycle | one-command POSIX installer, env probe, extras discovery, portable-config export or import, backup and restore (safe untar), check_update, apply_update, rollback (offline-safe), repair guidance |
| 2 | Capability router | capability-oriented routing, primary and fallback, health-based skip, per-connector circuit breaker, audit trail (credential-redacted) |
| 3 | Internet and content | keyless web search (DuckDuckGo), SSRF-guarded fetch, RSS or Atom (XXE-hardened), public GitHub repo research, Reddit, V2EX, YouTube (oEmbed + channel RSS), Xueqiu, Xiaoyuzhou; lawful-boundary stubs for platforms with no legal keyless read path |
| 4 | Local browser | optional adapter behind `[browser]` extras; isolated per-session context, cookies stay local, consent-gated write actions |
| 5 | Semantic research | SQLite FTS5 index, fast and deep search, domain include or exclude, extractive answer (grounded, no LLM), highlights, find-similar |
| 6 | Evidence and quality | persistent SQLite store, provenance envelopes, source-quality scoring (explainable factors), duplicate removal, change monitoring, deterministic contradiction detection, per-tenant scoping |
| 7 | MCP | local stdio MCP server, remote streamable-HTTP MCP with bearer auth, 8 stable tools (search, fetch, extract, query_evidence, capability_list, connector_health, export_research_packet, surface_status) |
| 8 | Plugin | plugin manifest, marketplace metadata, 4 slash commands, 8 specialised skills (see below), session-start health hook (local-only, no network egress) |
| 9 | Dev workflow | GitHub CLI and CI wiring, secret scan, changelog generator, repo-verification script, SBOM (CycloneDX), sigstore signing recipe |
| 10 | Provider-neutral backend | local auth (scrypt) + session tokens, SQLite queue with tenant scoping, filesystem SHA-addressable object store, RBAC matrix, JSON logs + Prometheus text emitter, event bus, per-tenant lifecycle |
| 11 | Security | SSRF, IP pinning, redirect re-validation, decompression bomb guard, size caps, credential redaction, no-hardcoded-credentials scan, no-silent-telemetry test, no-remote-skill-download test, live pip-audit vs OSV, licence-drift enforcement |
| 12 | Cross-surface and lifecycle | CLI, local MCP, remote MCP, Docker deploy scaffold, sigstore signing docs; per-Claude-surface activation matrix (see `docs/CLAUDE_SURFACE_SUPPORT.md`) |

Full row-level status: [`docs/FEATURE_TRACEABILITY.csv`](docs/FEATURE_TRACEABILITY.csv) and
[`docs/PRODUCTION_READINESS_REPORT.md`](docs/PRODUCTION_READINESS_REPORT.md).

## Skills

Eight specialised D-Eye skills ship with the plugin, each with a
`plugin/d-eye/skills/<name>/SKILL.md` file and a real Python
implementation in `deye/skills/<name>.py`. Each is invocable in
process via `deye.skills.invoke("<name>", ...)`.

| Skill | What it does |
|---|---|
| `research` | Decompose, search, fetch, cite, persist, and return a grounded extractive answer |
| `evidence` | Query, dedupe, change-check, export, delete captured evidence |
| `web_discovery` | Routed public-web search, fetch, or feed via the SSRF-hardened path |
| `browser_research` | Consent-gated isolated-browser interaction (opt-in) |
| `repository_research` | Read-only public repo metadata and latest commits |
| `source_quality` | Explainable quality scores and polarity or numeric contradiction detection |
| `offline_research` | Zero-network FTS5 and extractive answer over local evidence |
| `connector_builder` | Scaffold a new connector against the D-Eye contract |

Skill guide: [`docs/SKILLS_GUIDE.md`](docs/SKILLS_GUIDE.md).

## Connectors

Connector guide: [`docs/CONNECTOR_GUIDE.md`](docs/CONNECTOR_GUIDE.md).

Every connector uses `deye/connectors/base.py::safe_get` so it inherits
the SSRF gate, IP pinning, size cap, decompression guard, and redirect
re-validation. Every result is wrapped in an
`Envelope(trust=Trust(untrusted=True))`.

Keyless FOSS connectors: `search_duckduckgo`, `web_fetch`, `rss`,
`github_repo`, `reddit_search`, `reddit_fetch`, `v2ex_feed`,
`v2ex_fetch`, `youtube_fetch`, `youtube_channel_feed`, `xueqiu_fetch`,
`xiaoyuzhou_fetch`.

Optional external adapter: an opt-in third-party search adapter is
present in the code tree for operators who choose to plug in their
own API key. It is disabled by default and never appears on the
acceptance-test path.

Platform-boundary stubs: `twitter_x`, `linkedin`, `facebook`,
`instagram`, `bilibili`, `xiaohongshu`. Each is registered as a stub
that returns `HealthReport(status="missing")` with a truthful reason
(no lawful keyless read path exists today). The catalogue row is
preserved rather than silently dropped.

## Security model

See [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) and
[`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

Key invariants (each enforced by a test):

- Every URL passes through the SSRF gate (scheme allowlist, userinfo
  rejection, DNS resolve then IP pin, private, loopback, link-local,
  metadata block, cloud-metadata hostname and IP block,
  IPv4-mapped-IPv6 block).
- Every HTTPS connection uses SNI keyed to the real hostname and
  TLS-validates against it while TCP-connecting to the pinned IP
  (fixes DNS-rebinding TOCTOU).
- Every response is capped at 5 MiB by default and every decompression
  aborts at `cap + 1` bytes (defends gzip bombs).
- Every audit line, log entry, and exported packet passes through the
  credential redactor.
- Write actions are refused unless the caller has an explicit
  `ConsentPolicy.allow_write=True` AND the specific action name in
  `granted_actions`.
- Zero telemetry endpoints in tracked source (enforced by
  `tests/test_no_telemetry_and_no_remote_skills.py`).
- Zero remote skill downloading in the plugin (enforced by the same
  test).
- Live vulnerability audit against OSV via `scripts/run_pip_audit.sh`.
- Zero em, en, or non-breaking hyphen characters in user-facing files
  (enforced by `tests/test_ui_dashes.py`).

## Offline mode

Set `DEYE_OFFLINE=1` and D-Eye becomes zero-network:

- All connectors that require network report
  `HealthReport(status="missing")`.
- `deye lifecycle apply-update` and `provision_extra` refuse politely.
- The CLI, MCP server, evidence store, FTS5 search, extractive answer,
  and multi-tenant lifecycle continue to work over the local evidence
  corpus.

Details: [`docs/OFFLINE_MODE.md`](docs/OFFLINE_MODE.md).

## Configuration

- `DEYE_HOME` (default `~/.deye`): where config and evidence live.
- `DEYE_OFFLINE=1`: disable all network egress.
- `DEYE_HTTP_TOKEN`: required for the remote HTTP MCP server.
- `DEYE_BROWSER_PROFILES`: where the optional browser adapter keeps
  its per-session isolated profiles (owner-only permissions).
- `~/.deye/config.json`: search provider default, read-only default,
  optional-adapter secret references (`env:...` or `keychain:...`).

Config helpers: `deye lifecycle portable-export FILE`,
`deye lifecycle portable-import FILE`,
`deye lifecycle backup --dest DIR`,
`deye lifecycle restore ARCHIVE`.

## Local and remote MCP

**Local stdio MCP** (recommended):

```bash
./.venv/bin/python -m pip install -e '.[mcp]'
./.venv/bin/deye init-claude              # register with Claude Desktop or Code
./.venv/bin/deye init-claude --dry-run    # preview without writing
```

**Remote streamable-HTTP MCP** (cross-network clients):

```bash
./.venv/bin/python -m pip install -e '.[remote]'
export DEYE_HTTP_TOKEN="a-long-random-secret"
./.venv/bin/deye serve-http --host 0.0.0.0 --port 8080
```

Front the remote endpoint with a reverse proxy that handles TLS. See
[`docs/MCP_GUIDE.md`](docs/MCP_GUIDE.md) and
[`docker/`](docker/) for a compose spec.

**Cross-surface support** (Claude Desktop, Code, web, Projects,
Cowork): [`docs/CLAUDE_SURFACE_SUPPORT.md`](docs/CLAUDE_SURFACE_SUPPORT.md).
Cloud connector registration inside a Claude tenant is a user-owned
action; D-Eye ships the endpoint the tenant consumes but cannot
silently register itself into a third-party account.

## Practical workflows

### 1. Research continuous-pricing developments

```bash
deye research "continuous pricing airline revenue management" \
    --max-sources 5 -o packet.md
```

D-Eye searches, fetches the top 5 sources through the SSRF-guarded
path, extracts readable text, records each source with URL, timestamp,
and content hash into `~/.deye/evidence.db`, and writes a cited
Markdown packet plus a JSON companion.

- **Evidence created:** 1 packet + 5 source rows in
  `~/.deye/evidence.db`.
- **Limitations:** live network required; sources are untrusted.

### 2. Compare two public technical sources and identify disagreements

```python
from deye.skills import invoke
rows = invoke("evidence", action="query", query="continuous pricing")["rows"]
result = invoke("source_quality", rows=rows, min_confidence=0.5)
print(result["contradictions"])
```

Returns polarity and numeric contradiction candidates with confidence
scores. Every score exposes its factor breakdown.

### 3. Extract and store evidence from a webpage

```bash
deye fetch https://example.org/article
deye evidence "article"
```

The fetch runs through the SSRF-hardened path and persists a row. The
second command queries the persistent store.

### 4. Search a repository and explain the relevant implementation

```bash
deye repo python/cpython
```

Read-only public GitHub metadata plus recent commits, no key required.

### 5. Run a research task offline using local evidence

```bash
DEYE_OFFLINE=1 deye evidence "sqlite fts5"
```

Or via the skill:
`invoke("offline_research", query="sqlite fts5", mode="answer")`.

### 6. Query previously captured evidence

```bash
deye evidence "revenue management"
```

Full-text substring search over URLs, titles, and excerpts.

### 7. Export and delete one tenant's evidence

```python
from deye.skills import invoke
invoke("evidence", action="export", tenant="acme")
invoke("evidence", action="delete", tenant="acme", confirm_delete=True)
```

The default tenant is protected; deletion of a specific tenant
requires `confirm_delete=True`.

### 8. Use D-Eye through an MCP-compatible client

Install the plugin and register the MCP server (see the quick start).
Your client will see the 8 stable tools plus the 8 skills. Every
response is untrusted evidence with provenance.

### 9. Use a local browser connector with explicit consent

```python
from deye.core.policy import ConsentPolicy
from deye.skills import invoke
consent = ConsentPolicy(allow_write=True, granted_actions={"browser.click"})
invoke("browser_research", action="click",
       url="https://example.org", selector="button.submit", consent=consent)
```

Requires `pip install -e '.[browser]' && playwright install chromium`.
Without the extras, the skill returns `ok=False` with a clear reason.

## Troubleshooting

Full guide: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

- `deye doctor` says a connector is `missing`: run
  `deye lifecycle repair`.
- Remote MCP responds with `401`: set `DEYE_HTTP_TOKEN` before
  starting.
- Reddit fetch returns 403: Reddit's anti-bot filter rejects
  low-signal User-Agents; add an identifying UA per Reddit's guidance.
- Playwright not installed: run
  `pip install -e '.[browser]' && playwright install chromium`.
- pip-audit fails on the editable `deye`: run
  `sh scripts/run_pip_audit.sh`, which excludes the editable install.

## Developer guide

Full guide: [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md).

- Scaffold a new connector:
  `invoke("connector_builder", name="my_source", capability="fetch")`.
- Add a new skill: drop a Python module into `deye/skills/`, register
  a `SKILL` object, add a `plugin/d-eye/skills/<name>/SKILL.md`, add
  an acceptance test in `tests/test_skills.py`.
- Run everything: `./.venv/bin/python -m pytest -q -rs`.
- Verify no forbidden dashes in the UI:
  `python3 scripts/scan_ui_dashes.py`.
- Verify licence compliance:
  `python3 scripts/scan_licences.py`.

## Validation status

Live traceability (`docs/FEATURE_TRACEABILITY.csv`), regenerated on
every workbook or CSV update:

- **PRODUCTION READY:** rows whose implementation, tests, security
  checks, and acceptance evidence all pass.
- **IMPLEMENTED BUT NOT FULLY VERIFIED:** code path exists and is
  unit-tested; full verification blocked by an environmental
  constraint (see the row's `acceptance_result`).
- **PARTIAL:** architecture and interfaces landed; concrete gaps
  documented.
- **BLOCKED BY EXTERNAL PLATFORM:** each with a specific reason in
  [`reports/REMAINING_EXTERNAL_BLOCKERS.md`](reports/REMAINING_EXTERNAL_BLOCKERS.md).

Test totals verified in this environment: **239 passed / 0 failed / 8
skipped** (the 8 skips are live-network tests that need direct DNS
this sandbox does not provide; identical tests pass on network-
permissive hosts). Bandit: 0 HIGH / 0 MEDIUM / 8 LOW (informational
subprocess-usage flags). Live pip-audit against OSV: no known
vulnerabilities across 86 installed packages. See
[`docs/TEST_EVIDENCE.md`](docs/TEST_EVIDENCE.md).

## Compatibility

- Verified: macOS 15 (Darwin 24.6.0), Python 3.14.3.
- Documented but not verified in this environment: Linux, Windows.
  The install script and CLI paths are POSIX + `subprocess`-based; no
  known Windows-only breakage but no automated Windows CI run yet.

## Current limitations

- Live-network smoke of every connector requires a host with direct
  outbound DNS. This sandbox routes outbound HTTP through a proxy,
  and D-Eye's SSRF-hardened fetch path intentionally bypasses HTTP
  proxies. Live tests skip cleanly with an honest reason on such hosts.
- Live remote-MCP hosted deployment: shipped as documentation and a
  Docker compose spec; no live hosted endpoint has been stood up from
  this session.
- Live sigstore-signed release: `scripts/sign_release.sh` and
  `docs/SIGNED_RELEASE.md` ship the recipe; the OIDC-browser step is a
  user action.
- Claude cross-surface activation (Web, Projects, Cowork): a
  platform-side registration action owned by the tenant admin.
- 6 platform-boundary stubs (Twitter/X, LinkedIn, Facebook, Instagram,
  Bilibili, Xiaohongshu) are BLOCKED BY EXTERNAL PLATFORM: no lawful
  keyless read path exists.

## Licence and attribution

MIT. See [`LICENSE`](LICENSE).

Attribution for third-party projects that informed D-Eye's design and
every runtime and tooling dependency licence lives in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) at the repo root.

## Roadmap

Concrete next steps (each with a row in the traceability CSV):

- Live-network smoke of every connector on a network-permissive CI
  runner.
- Cross-platform install verification on Linux and Windows runners.
- Live sigstore-signed release with reproducible-build verification.
- Live remote-MCP hosted deployment (`deye serve-http` behind a TLS
  reverse proxy).
- Playwright extras and live browser integration test.
- Optional local-embeddings extras (`[embeddings]`: fastembed +
  sqlite-vec) with a documented adapter contract.

No vague marketing language. Every capability is either shown as
PRODUCTION READY with executed evidence or labelled honestly.
