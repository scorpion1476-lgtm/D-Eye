# D-Eye — CLI Guide

Every command below assumes an active D-Eye venv:

```bash
cd repository/deye
./.venv/bin/deye <command>
```

## Top-level subcommands

| Command | What it does |
|---|---|
| `deye setup` | One-time: write `~/.deye/config.json` with FOSS defaults. |
| `deye status` | Show version + home dir + read-only default + search provider. |
| `deye capabilities` | List every capability the router knows. |
| `deye connectors` | List every registered connector with licence + cost. |
| `deye doctor` | Health-check every connector. |
| `deye doctor --surfaces` | Report which Claude surfaces D-Eye can reach. |
| `deye search QUERY` | Run one web search. |
| `deye fetch URL` | Fetch + extract one URL through the SSRF-guarded path. |
| `deye research QUERY [--max-sources N] [-o OUT]` | Full research packet. |
| `deye evidence QUERY` | Query the persistent evidence store. |
| `deye repo OWNER/NAME` | Public GitHub repo inspection. |
| `deye graph [QUERY] [--markdown -o OUT]` | Build evidence graph + contradiction report. |
| `deye serve-http --host H --port P` | Run the remote HTTP MCP (requires `DEYE_HTTP_TOKEN`). |
| `deye init-claude [--dry-run] [--run-claude-code]` | Register D-Eye with Claude Desktop / Code. |
| `deye lifecycle <verb>` | See below. |

## Lifecycle subcommands

| Verb | What it does |
|---|---|
| `env` | Detect OS, Python, browsers, CLIs. |
| `extras` | Report which optional extras are available. |
| `repair` | Actionable repair suggestions. |
| `status` | Aggregate env + extras + repair report. |
| `backup --dest DIR` | tar.gz `DEYE_HOME` into DIR. |
| `restore ARCHIVE [--overwrite]` | Restore a backup. |
| `portable-export FILE` | Export a redacted portable config JSON. |
| `portable-import FILE` | Import a portable config JSON (allowlisted keys only). |
| `check-update` | Report current + available version (offline-safe). |
| `apply-update SPEC [--dry-run]` | Install a specific pip spec. |
| `rollback VERSION` | Reinstall a specific D-Eye version. |
| `uninstall [--remove-home]` | pip-uninstall + optionally back up + remove `DEYE_HOME`. |

## Environment variables

- `DEYE_HOME` (default `~/.deye`)
- `DEYE_OFFLINE=1` — disable every network egress
- `DEYE_HTTP_TOKEN` — required by `deye serve-http`
- `DEYE_BROWSER_PROFILES` — where browser profiles live (owner-only)

## Exit codes

- `0` success
- `1` command-level failure (message printed via redact())
- `2` remote / extras missing (e.g., `serve-http` without the `[remote]` extra)
