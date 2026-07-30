# Third-party notices

D-Eye is an independent, clean-room implementation. This file records
attribution for the third-party projects whose architecture or
patterns informed D-Eye's design, plus every third-party runtime and
tooling dependency D-Eye can install.

None of the projects listed here are bundled inside D-Eye or made
mandatory. No source file, credential, private API, brand, or configuration
value from these projects is included in D-Eye's tracked source.

## Design pattern attribution (patterns only — no code copied)

| Upstream project | Licence | Copyright | Pattern attribution |
|---|---|---|---|
| Agent-Reach | MIT | 2025 Agent Eyes / "Neo Reid" — https://github.com/Panniantong/Agent-Reach | The capability-router idea and the URL host-allowlist pattern were studied. D-Eye's routing lives in `deye/core/router.py` + `deye/core/registry.py`; the URL host-allowlist was re-implemented and hardened into `deye/core/policy.py` (adds SSRF gate, IP pinning against DNS-rebind TOCTOU, redirect re-evaluation, decompression-bomb guard, private-IP + cloud-metadata blocks). None of the Agent-Reach source code is present in D-Eye. |
| mcpmarket-plugin (MCPmarket) | MIT | https://github.com/knoxgraeme/mcpmarket-plugin | Claude-plugin manifest shape and hook layout were studied. D-Eye's plugin ships NO remote bearer token, NO remote-skill-sync path, and NO PostToolUse telemetry — all of which the studied plugin had. |
| OpenCLI | Apache-2.0 | — | Referenced during design as one option for optional user-controlled browser adapters. Not implemented as a runtime dependency. |

**Security note:** the mcpmarket plugin archive that was reviewed at design
time contained a live-looking bearer token inside its `.mcp.json`. That
value was treated as compromised, is NOT reproduced anywhere in D-Eye's
tracked source, and should be rotated by its owner if not already done.

## Runtime dependencies (Python packages)

The core install path is standard-library only. Optional extras install
FOSS packages; every one is documented in `docs/DEPENDENCY_AND_LICENCE_POLICY.md`
with its SPDX licence, pin, purpose, and replacement path.

Highlights:

| Package | Licence | Extras group |
|---|---|---|
| mcp[cli] | MIT | `[mcp]`, `[remote]` |
| uvicorn | BSD-3-Clause | `[remote]` |
| starlette | BSD-3-Clause | `[remote]` |
| keyring | MIT | `[secrets]` |
| feedparser | BSD-2-Clause | `[rich]` |
| requests | Apache-2.0 | `[rich]` |
| playwright | Apache-2.0 | `[browser]` (planned) |
| fastembed | Apache-2.0 | `[embeddings]` (planned) |
| sqlite-vec | Apache-2.0 | `[embeddings]` (planned) |
| argon2-cffi | MIT | `[backend]` (planned) |
| prometheus_client | Apache-2.0 | `[backend]` (planned) |
| pytest | MIT | `[dev]` |
| ruff | MIT | `[dev]` |
| bandit | Apache-2.0 | build tool |
| pip-audit | Apache-2.0 | build tool |
| cyclonedx-bom | Apache-2.0 | build tool |

Full installed-tree licence report: run `python3 scripts/scan_licences.py`.
Full SBOM: `repository/deye/sbom.json` (CycloneDX).

## Third-party services referenced by optional adapters (not required)

Optional adapters may consume the following external services. None are
required by the D-Eye core, no key or account is needed to install or
operate D-Eye, and each adapter is off by default.

- Exa (paid search API) — optional adapter kept in the code tree so an
  operator with a key can use it; kept off the acceptance-test path.

## Icon assets

The D-Eye icon assets under `assets/branding/` were supplied by the D-Eye
project owner; use is subject to the project MIT licence. See
`assets/branding/MANIFEST.json` for canonical hashes and provenance.
