# D-Eye troubleshooting

**`deye: command not found`** - the package installed but the scripts dir isn't
on PATH. Run `python -m deye.cli ...`, or add your Python user-scripts dir to PATH.

**A fetch says `blocked by policy: non-public IP ...`** - working as intended.
D-Eye refuses to fetch loopback/private/metadata addresses (SSRF protection). If
you genuinely need an internal host, that requires an explicit allowlist change
and is intentionally not a casual setting.

**Search returns few or no results** - the keyless default depends on a public
endpoint that can rate-limit. Wait and retry, or configure the optional Exa
adapter (`EXA_API_KEY`) for higher-quality results.

**MCP server won't start / "mcp SDK not installed"** - run
`python -m deye.mcp_server --selftest` to verify the handlers, or install the
transport with `pip install -e '.[mcp]'`.

**Claude doesn't see D-Eye tools** - run `deye doctor --surfaces`. Remember web
and local surfaces use different mechanisms; you must register the one for the
surface you're using.

**Nothing writes to `~/.deye`** - run `deye setup` first; it creates the
owner-only home directory.
