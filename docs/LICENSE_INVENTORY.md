# D-Eye licence & dependency inventory

**Attribution note.** This file lists only D-Eye's own licence and its
runtime + optional dependency licences. Attributions to third-party
projects that informed D-Eye's design live in `THIRD_PARTY_NOTICES.md`
at the repo root, per the D-Eye documentation policy that keeps
external product names out of user-facing product docs.

## D-Eye itself
MIT (see `LICENSE`). All third-party attribution lives in
`THIRD_PARTY_NOTICES.md` and `NOTICE`.

## Runtime dependencies of the core vertical slice
**None.** The core (`deye/core`, `deye/connectors`, `deye/lifecycle`,
`deye/research`, `deye/backend`, CLI, MCP facade) runs on the Python
standard library only, so the FOSS baseline has zero third-party runtime
licence obligations.

## Optional extras (installed only if you opt in)

| Extra | Package | Licence | Purpose |
|---|---|---|---|
| `mcp` | `mcp[cli]` | MIT | local stdio MCP server transport |
| `remote` | `mcp[cli]` | MIT | streamable-HTTP transport |
| `remote` | `starlette` | BSD-3-Clause | ASGI app + auth middleware |
| `remote` | `uvicorn` | BSD-3-Clause | ASGI server |
| `secrets` | `keyring` | MIT | OS-keychain secret references |
| `rich` | `feedparser` | BSD-2-Clause | richer feed parsing |
| `rich` | `requests` | Apache-2.0 | alternative HTTP client |
| `browser` | `playwright` | Apache-2.0 | optional local browser adapter |
| `embeddings` | `fastembed` | Apache-2.0 | optional local text embeddings |
| `embeddings` | `sqlite-vec` | Apache-2.0 | optional local vector index |
| `backend` | `argon2-cffi` | MIT | optional password hashing |
| `backend` | `prometheus_client` | Apache-2.0 | optional Prometheus scrape endpoint |
| `dev` | `pytest` | MIT | tests |
| `dev` | `ruff` | MIT | lint |

## Build-time tools (not required at runtime)

| Tool | Licence | Purpose |
|---|---|---|
| `bandit` | Apache-2.0 | static analysis (SAST) |
| `pip-audit` | Apache-2.0 | live OSV dependency audit |
| `cyclonedx-bom` | Apache-2.0 | SBOM generation |
| `sigstore` (release-time only) | Apache-2.0 | keyless artefact signing |

## Policy
- Keep the core permissive.
- Isolate any copyleft or hosted component behind an opt-in extras group.
- Preserve notices required by each licence.
- Obtain legal review before commercial redistribution of any bundled
  copyleft dependency.
- Vulnerability audit runs live against OSV.dev — see
  `docs/DEPENDENCY_AND_LICENCE_POLICY.md` and `scripts/run_pip_audit.sh`.

## Copyleft / source-available deny list

D-Eye does not include any dependency with an AGPL, SSPL, Business Source
Licence, Elastic Licence, Commons Clause, or proprietary source-available
licence. The `scripts/scan_licences.py` compliance script fails on any
denied licence in the installed dep tree.
