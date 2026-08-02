<p align="center">
  <img src="assets/brand/logo.png" alt="D-Eye" width="360">
</p>

<p align="center">
  <b>A FOSS-first, local-first capability and evidence layer that gives Claude and any MCP client safe, cited access to the web, with security decided outside the model.</b>
</p>

<div align="center">

![License: MIT](https://img.shields.io/badge/License-MIT-3da639.svg)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776ab.svg)
![Tests](https://img.shields.io/badge/tests-422%20passing%20on%20clean%20clone-2c7a3f.svg)
![Status](https://img.shields.io/badge/status-working%20audited%20core-1f6feb.svg)
![FOSS--first](https://img.shields.io/badge/FOSS--first-yes-6f42c1.svg)
![Local--first](https://img.shields.io/badge/local--first-yes-a07020.svg)

</div>

D-Eye is a local tool that gives Claude and other AI assistants a safe, honest way to use the web. It runs on your own machine, needs no paid keys for its core, and turns web research into cited, verifiable results instead of a black box: every answer carries its sources, and the rules about what may be fetched are enforced outside the model, so a web page can never talk your assistant into doing something it shouldn't. Most of its catalogued capabilities are built and working today; a small number are still in progress or depend on outside platforms, and those are listed openly.

---

## Contents

- [Why D-Eye](#why-d-eye)
- [Capabilities](#capabilities)
- [Quick start](#quick-start)
- [Architecture](#architecture)
- [Practical use cases](#practical-use-cases)
- [Security posture](#security-posture)
- [MCP tools](#mcp-tools)
- [Status, honestly](#status-honestly)
- [Repository layout](#repository-layout)
- [Contributing](#contributing)
- [Security policy](#security-policy)
- [License](#license)

## Why D-Eye

Most agent stacks reach the web in ways that are unsafe, unverifiable, or locked behind paid keys. D-Eye fixes that at the layer between the model and the network, with deterministic policy that the model never gets to override.

| Problem | D-Eye's answer |
|---|---|
| Agents fetch unsafely and can be pointed at internal addresses or cloud metadata. | Every fetch passes an SSRF gate that blocks private, loopback, link local, and cloud metadata addresses, then pins the TCP connection to the vetted IP so a hostname cannot rebind to a private target between check and connect. |
| Answers are uncited and cannot be audited. | Every result is captured with its source URL, a retrieval timestamp, and a content hash, and research is returned as a cited packet, not a black box. |
| Fetched text tries to steer the model ("ignore previous instructions"). | Retrieved content is labelled untrusted evidence, never instructions, and security decisions run deterministically outside the model. |
| Many sources need a paid API key or a hosted account. | The core is keyless and uses only the Python standard library. Paid or hosted adapters are optional, off by default, and never on the acceptance path. |

## Capabilities

| Capability | What you get | Needs setup? |
|---|---|---|
| Keyless web search | Search the public web through the DuckDuckGo HTML endpoint, no key or account. | No |
| Webpage fetch and extraction | Policy gated fetch through the hardened path, plus readable text extraction. | No |
| RSS and Atom | Feed reader hardened against XXE and entity expansion. | No |
| GitHub | Read only public repository metadata and recent commits. | No |
| Reddit, V2EX, and similar community connectors | Keyless reads routed through the same SSRF hardened fetch path. | No |
| Semantic research with cited answers | Local SQLite FTS5 index with grounded extractive answers and a cited research packet. | No |
| Evidence store | Persistent SQLite store with provenance envelopes and per tenant scoping. | No |
| MCP server | Ten stable tools over a local stdio server, or a remote streamable HTTP server. | Local: no. Remote: set a bearer token. |
| Local browser adapter | Optional, opt in, isolated per session context with consent gated actions. | Optional extra |
| Hosted search adapter | Optional, bring your own key. Disabled by default; falls back to the keyless search. | Optional key |

## Quick start

Prerequisite: Python 3.10 or newer. The core install pulls zero runtime dependencies (standard library only).

```bash
# 1. install the core (FOSS, no keys, no accounts)
git clone https://github.com/scorpion1476-lgtm/D-Eye D-Eye
cd D-Eye
python3 -m venv .venv
./.venv/bin/python -m pip install -e .

# 2. one time setup (writes ~/.deye/config.json with FOSS defaults, no secrets)
./.venv/bin/deye setup
./.venv/bin/deye doctor          # confirm connectors are healthy

# 3. run some research (search, fetch, cite, persist)
./.venv/bin/deye research "continuous pricing airline revenue management" \
    --max-sources 5 -o packet.md

# 4. query what was captured
./.venv/bin/deye evidence "continuous pricing"
```

Register D-Eye with Claude Desktop and Claude Code (local stdio MCP):

```bash
./.venv/bin/python -m pip install -e '.[mcp]'
./.venv/bin/deye init-claude              # writes the local MCP config
./.venv/bin/deye init-claude --dry-run    # preview, change nothing
```

The `research` command searches, fetches the top sources through the SSRF guarded path, extracts readable text, records each source with its URL, timestamp, and content hash into `~/.deye/evidence.db`, and writes a cited Markdown packet plus a JSON companion. Full walkthrough: [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

## Architecture

<p align="center">
  <img src="assets/brand/architecture.png" alt="D-Eye architecture: request lifecycle, capabilities, evidence and data, and the security foundation">
</p>

D-Eye is organised in four layers:

1. **Request lifecycle.** An MCP client (Claude Desktop, Claude Code, or any MCP client) or the CLI issues a capability request. A capability router picks a healthy, policy compliant connector, falls back on failure, and opens a circuit breaker on a repeatedly failing backend. The result comes back as a cited, provenance tracked research packet in Markdown or JSON.
2. **Capabilities.** Keyless connectors (web search, fetch, RSS, GitHub, Reddit, V2EX and more), a semantic research layer with local keyword search and grounded extractive answers, and the `deye` command line.
3. **Evidence and data.** A persistent SQLite evidence store, provenance for every result (source, timestamp, content hash), and an evidence graph that surfaces claims, relationships, and contradiction candidates.
4. **Security foundation.** Decided deterministically, outside the model: an SSRF guard with private IP and cloud metadata blocking and connection level IP pinning, a consent gate that keeps writes off by default, credential redaction, and a policy engine that runs before every fetch.

## Practical use cases

- **Give Claude Desktop safe, cited web access.** Register the local MCP server; the client sees a small, stable tool set, and every response is untrusted evidence with provenance.
- **Produce a sourced research packet on a topic.** `deye research "topic" --max-sources 5 -o packet.md` returns a cited Markdown packet plus a JSON companion, with each source hashed and stored.
- **Monitor RSS and Atom feeds for changes.** Pull a feed through the XXE hardened reader and compare against previously captured evidence to detect what changed.
- **Read a public GitHub repository and its issues.** `deye repo owner/name` returns read only repository metadata and recent commits, no key required.
- **Query previously gathered evidence, offline.** `DEYE_OFFLINE=1 deye evidence "sqlite fts5"` runs full text search over the local corpus with zero network egress.

## Security posture

Each control below is genuinely implemented in the tracked source and covered by a test.

| Control | What it does |
|---|---|
| SSRF and policy guard | Scheme allowlist, URL userinfo rejection, and a post resolution IP check that blocks private, loopback, link local, multicast, reserved, and cloud metadata addresses. Fails closed if a host resolves to any non public address. |
| Connection level IP pinning | The socket connects to the vetted IP while TLS still validates against the real hostname (SNI), closing the DNS rebinding time of check to time of use gap. |
| Read only by default, consent gate for writes | Write, browser, and side effecting actions are refused unless a human grants explicit consent for that specific action. |
| No hard coded tokens | Enforced by a test that scans the tracked tree for credential shaped strings. |
| Secret redaction | Every audit line, log entry, and exported packet passes through a credential redactor before it is written or emitted. |
| Untrusted evidence | Every fetched result is tagged untrusted and carries its source, timestamp, and content hash; the model is told never to obey text found inside evidence. |
| Decompression and size caps | Responses are size capped and decompression aborts past the cap, defending against gzip bombs. |
| Deterministic policy | All of the above is decided outside the model, in `deye/core/policy.py` and the connector fetch path, not by the LLM. |

More detail: [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

## MCP tools

The server exposes a small, stable tool surface. Raw scrapers and shell access are deliberately not exposed to the model.

| Tool | What it does |
|---|---|
| `capability_list` | List the capabilities and tools the server offers. |
| `connector_health` | Report the health of every registered connector. |
| `search` | Keyless public web search, returned as redacted content with artifacts. |
| `fetch` | Policy gated fetch and extract of a single URL. |
| `extract` | Convert a block of HTML to readable text. |
| `export_research_packet` | Search, fetch, cite, persist, and return a grounded Markdown packet. |
| `query_evidence` | Query the persistent evidence store. |
| `semantic_search` | Keyless local semantic search over stored evidence, returning a grounded, cited answer. |
| `repo_inspect` | Read only public GitHub repository metadata and recent commits. |
| `surface_status` | Report, honestly, which client surfaces D-Eye can be active in. |

Local stdio and remote streamable HTTP transports are documented in [`docs/MCP_GUIDE.md`](docs/MCP_GUIDE.md). The remote transport requires a bearer token (`DEYE_HTTP_TOKEN`) and should sit behind a TLS terminating reverse proxy.

## Status, honestly

D-Eye is deliberately truthful about what is proven and what is not.

- **Tests (verified in this environment on 2026-08-02):** the full suite runs with 0 failures on a fresh public clone via `scripts/clean_clone_gate.sh`, which installs the documented extras plus `.[browser]` and `playwright install chromium`, then runs everything (422 passed, 6 skipped, 0 failed with every live source reachable). Structural browser tests cover the Playwright-absent code path and skip when the extra is present; the live headless browser tests run when it is present. Live-network tests skip when a source is unreachable or rate-limited and pass when it is reachable, so the exact passing count dips by one or two as the network varies.
- **Static analysis:** Bandit reports 0 high and 0 medium findings; the low findings are the expected fixed argument subprocess calls and defensive exception handling.
- **Feature catalogue:** under a strict evidence rubric, 153 of 167 catalogued capabilities are PRODUCTION READY, each backed by a real acceptance test that exercises the feature and passes on a clean clone. The other 14 are blocked by an external platform (a login or anti-bot wall, a hosted GitHub/Claude account surface, or a container runtime the FOSS gate excludes), each with a precise recorded reason. No row remains implemented-but-not-verified or partial; none is inflated.
- **Not claimed:** D-Eye as a whole is not production ready, and no claim of 100 percent completion is made.

Honest roadmap:

- A live hosted remote MCP endpoint (the transport and bearer auth ship and are tested in-process today; no public hosted endpoint has been stood up).
- Cross operating system installer verification on Linux and Windows runners.
- The platform blocked community connectors, once a lawful keyless read path exists.

Shipped since the last revision: FOSS signed-release and bundle verification (OpenSSL Ed25519 signature over a SHA256SUMS manifest), the live headless browser edge (Playwright), keyless local semantic search as the default (a local hashing embedding plus a local vector index), usage and cost reporting for optional adapters, a keyless Bilibili public video-info connector, and a `repo_inspect` GitHub tool on the MCP surface.

## Repository layout

```
D-Eye/             (the clone root is the package root)
  deye/            core package: core (policy, router, evidence, provenance, redact),
                   connectors, research, skills, backend, browser, lifecycle
  tests/           test suite (unit, integration, live network, subprocess, browser)
  docs/            guides (quickstart, MCP, connectors, skills, offline, threat model)
  plugin/d-eye/    Claude plugin: manifest, marketplace, skills, commands, hooks
  assets/brand/    the approved logo and the architecture diagram
  scripts/         build, SBOM, secret scan, dash scan, repo verification
  docker/          remote MCP compose scaffold
  pyproject.toml   packaging; the core has zero runtime dependencies
```

## Contributing

Start with [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md). Install the dev extra first, which provides pytest and the pip-audit tool used by the live security test: `./.venv/bin/python -m pip install -e '.[dev]'`. Then run the suite with `./.venv/bin/python -m pytest -q -rs`. The MCP and remote tests use the `mcp` and `remote` extras, and the browser tests use `.[browser]` plus `playwright install chromium`; without those extras the affected tests skip cleanly. Check for forbidden dash characters with `python3 scripts/scan_ui_dashes.py`, and scaffold a new connector against the D-Eye contract with the `connector_builder` skill. New network or parse paths must route through `deye/connectors/base.py` and `deye/core/policy.py` so they inherit the SSRF gate, IP pinning, size cap, decompression guard, and redirect re-validation.

## Security policy

Report vulnerabilities per [`SECURITY.md`](SECURITY.md). Please do not open a public issue for an undisclosed vulnerability.

## License

MIT. See [`LICENSE`](LICENSE). Attribution for third party projects that informed the design, and every runtime and tooling dependency license, lives in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
