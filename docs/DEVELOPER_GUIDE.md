# D-Eye - Developer Guide

## Project layout

```
repository/deye/
├── deye/
│   ├── app.py               # router + capability wiring
│   ├── cli.py               # `deye` CLI
│   ├── extract.py           # HTML → readable text
│   ├── init_claude.py       # Claude Desktop / Code registration
│   ├── mcp_server.py        # local stdio MCP + FastMCP wiring
│   ├── remote.py            # remote streamable-HTTP MCP + bearer auth
│   ├── surfaces.py          # cross-surface (Claude Desktop/Code/Web/...)
│   ├── core/
│   │   ├── policy.py        # SSRF, IP pinning gate, ConsentPolicy, Limits
│   │   ├── router.py        # capability router + circuit breaker + audit
│   │   ├── registry.py      # ConnectorManifest, HealthReport, Registry
│   │   ├── provenance.py    # Envelope, Source, Trust, Evidence, ResearchPacket
│   │   ├── evidence.py      # SQLite-backed EvidenceStore + multi-tenant scoping
│   │   ├── graph.py         # entity/claim graph + contradiction detection
│   │   ├── quality.py       # source-quality scoring, dedup, change_monitor
│   │   ├── redact.py        # credential-shaped redaction
│   │   └── config.py        # Config + secret-reference resolution
│   ├── connectors/
│   │   ├── base.py          # safe_get, safe_post (SSRF + pin + decompress + redirect)
│   │   ├── web_fetch.py, web_search.py, rss.py, github_repo.py, reddit.py,
│   │   ├── v2ex.py, youtube.py, xueqiu.py, xiaoyuzhou.py, social_stub.py
│   ├── lifecycle/           # env detect, extras, backup/restore, update, rollback
│   ├── research/            # FTS5 index + fast/deep/domain/highlights/similar/answer
│   ├── browser/             # optional Playwright adapter + profiles + CookieBoundary
│   ├── backend/             # optional auth + queue + storage + RBAC + obs + events
│   └── skills/              # 8 D-Eye skills (research, evidence, web_discovery, ...)
├── plugin/d-eye/
│   ├── plugin.json          # plugin manifest + testable safety flags
│   ├── mcp.json             # local stdio MCP server config
│   ├── marketplace.json     # marketplace metadata
│   ├── hooks/hooks.json     # SessionStart local shim
│   ├── hook-shim.sh         # local `deye doctor` invocation
│   ├── commands/            # 4 slash commands
│   └── skills/              # 8 SKILL.md files, one per D-Eye skill
├── tests/                   # test suite (358 passing; see docs/TEST_REPORT.md)
├── docs/                    # user-facing guides
└── scripts/                 # gen_sbom, scan_licences, run_pip_audit, verify_repo, ...
```

## Running everything

```bash
./.venv/bin/python -m pytest -q -rs                    # full test suite
./.venv/bin/python -m bandit -r deye                   # SAST
sh scripts/run_pip_audit.sh                            # live OSV audit
./.venv/bin/python scripts/scan_licences.py            # licence drift
./.venv/bin/python scripts/gen_sbom.py                 # CycloneDX SBOM
```

## Adding a new connector

Use the `connector_builder` skill (fastest path):

```python
from deye.skills import invoke
r = invoke("connector_builder",
           name="my_source", capability="fetch",
           description="What this connector reads.",
           license="MIT",
           out_path="deye/connectors/my_source.py")
```

Then:

1. Customise `run()` for the target host + response parsing.
2. Register the manifest in `deye/app.py::build_registry`.
3. Add `tests/test_connector_my_source.py` with monkeypatched `safe_get`.
4. Document it in `docs/CONNECTOR_GUIDE.md`.
5. Run `pytest`.

Never call raw `urllib.request` or `requests` - always go through
`deye.connectors.base.safe_get` / `safe_post` so the SSRF + size +
decompression + redirect-re-eval invariants hold.

## Adding a new skill

1. Create `deye/skills/<name>.py` with a `run(...)` function and a
   top-level `SKILL = Skill(...)` object.
2. Import + register in `deye/skills/__init__.py::REGISTRY`.
3. Add `plugin/d-eye/skills/<name>/SKILL.md` with YAML frontmatter
   (name, description, version, tools, tags).
4. Add tests in `tests/test_skills.py`.
5. Run `pytest tests/test_skills.py`.

The registry test enforces name-consistency between the Python module
and the SKILL.md file.

## Security expectations

- Every URL goes through `evaluate_url` (part of `safe_get`). Never
  add a code path that bypasses it.
- Every audit line, log line, and exported packet passes through
  `redact()` (or `redact_mapping()` for header dicts).
- Every write action must be gated by `ConsentPolicy`.
- Every new dep must be added to `docs/DEPENDENCY_AND_LICENCE_POLICY.md`
  with SPDX licence + pin + replacement path.
- `bandit -r deye` must remain 0 HIGH / 0 MEDIUM. LOW findings must be
  informational (subprocess-usage flags, defensive try/except/pass).

## Commit style

- Conventional prefixes: `feat:`, `fix:`, `security:`, `docs:`,
  `test:`, `chore:`, `refactor:`, `deps:`, `ci:`, `build:`.
- Prefix subject line drives the changelog bucketing done by
  `scripts/gen_changelog.py`.
- Commit body: what changed, why, and the acceptance evidence.

## Testing style

- Tests must be deterministic. Live-network tests skip cleanly when
  the endpoint is unreachable.
- Prefer real acceptance evidence over mocks where the sandbox
  permits: real subprocesses, real SQLite persistence, real seeded
  data.
- Every promotion of a row to PRODUCTION READY requires the acceptance
  test to actually exist and pass.
