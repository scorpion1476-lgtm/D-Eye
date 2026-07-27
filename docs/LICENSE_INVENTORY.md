# D-Eye license & dependency inventory

## D-Eye itself
MIT (see `LICENSE`). Attribution to studied projects in `NOTICE`.

## Runtime dependencies of the core vertical slice
**None.** The core (`deye/core`, connectors, CLI, MCP facade) runs on the Python
standard library only, so the FOSS baseline has zero third-party runtime licence
obligations.

## Optional extras (installed only if you opt in)
| Extra | Package | Licence | Purpose |
|---|---|---|---|
| `mcp` | `mcp[cli]` | MIT | real stdio MCP server transport |
| `secrets` | `keyring` | MIT | OS-keychain secret references |
| `rich` | `feedparser` | BSD-2-Clause | richer feed parsing |
| `rich` | `requests` | Apache-2.0 | alternative HTTP client |
| `remote` | `mcp[cli]` | MIT | streamable-http transport |
| `remote` | `starlette` | BSD-3-Clause | ASGI app + auth middleware |
| `remote` | `uvicorn` | BSD-3-Clause | ASGI server |
| `dev` | `pytest` | MIT | tests |
| `dev` | `ruff` | MIT | lint |

## Projects studied for design (NOT vendored)
| Project | Licence | How treated |
|---|---|---|
| Agent-Reach | MIT | patterns re-implemented clean; credited in NOTICE |
| mcpmarket-plugin | MIT | plugin shape studied; token/remote-sync/telemetry removed |
| OpenCLI | Apache-2.0 | optional user-controlled browser edge (roadmap) |
| Exa | Proprietary (hosted) | optional adapter, never required |
| Firebase / Genkit | Apache-2.0 (Genkit) / proprietary (Firebase) | optional deploy adapter only |
| Firecrawl | **AGPL-3.0** | **NOT used.** If ever added, must be isolated behind a separate optional service and legally reviewed, because AGPL network-use obligations would otherwise reach the whole platform. |

Policy: keep the core permissive, isolate any copyleft/hosted component behind
an optional service boundary, preserve notices, and obtain legal review before
commercial redistribution.
