# D-Eye plugin for MCP-compatible clients

Registers the **local** D-Eye MCP server (`python -m deye.mcp_server`)
and eight specialised D-Eye skills that tell the agent when to use
D-Eye's search / fetch / research / evidence / browser / repository /
source-quality / offline / connector-builder tools.

Skills (each with its own `SKILL.md`):

- `research`             - decompose → search → fetch → cite → store
- `evidence`             - record, dedupe, change-monitor, export, delete
- `web_discovery`        - public web + RSS + repositories, all read-only
- `browser_research`     - isolated local browser, consent-gated writes
- `repository_research`  - repository + file + issue + release lookups
- `source_quality`       - quality score + contradiction analysis
- `offline_research`     - no-network mode over local evidence + indexes
- `connector_builder`    - scaffold a new connector against the D-Eye contract

Safety properties (each asserted as a testable manifest flag):

- read-only by default; consent required for any write action;
- no remote skill downloading;
- no silent telemetry;
- no hard-coded bearer token or API key inside any plugin file;
- browser cookies never uploaded off-device.

Install with an MCP-compatible plugin manager, e.g.:

```
claude plugin install ./plugin/d-eye
```

Verify locally with:

```
deye doctor --surfaces
```

The plugin points at a local stdio MCP server (`python -m
deye.mcp_server`). For remote-HTTP MCP see `docs/MCP_GUIDE.md`.
