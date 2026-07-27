# Claude Desktop & Claude Code configuration examples

> Prerequisite for local mode: install the package first so `deye` and the
> module are importable: `pip install deye` (or `pip install -e .` from a clone).
> The plugin does NOT install Python for you and does NOT assume the repo is the
> working directory.

## Claude Code (user scope -> all your projects)
```bash
claude mcp add --scope user deye -- python3 -m deye.mcp_server
claude mcp list          # should show: deye
deye doctor --surfaces
```

## Claude Desktop (also covers Code-in-Desktop and local Cowork)
Add to Desktop's MCP servers config:
```json
{
  "mcpServers": {
    "deye": {
      "command": "python3",
      "args": ["-m", "deye.mcp_server"]
    }
  }
}
```
If `python3` is not on Desktop's PATH, use the absolute interpreter path from
`which python3` (macOS/Linux) or `where python` (Windows).

## Claude web Chat / Projects (remote connector -- different mechanism)
Local stdio is NOT reachable from the web. Deploy the remote service
(`docs/REMOTE_DEPLOYMENT.md`) and add its `https://.../mcp` URL + bearer token as
a custom connector.

## DEYE_HOME
Defaults to `~/.deye` (created owner-only by `deye setup`). Override by setting
the `DEYE_HOME` environment variable in your shell before launching Claude; do
not rely on `~` expansion inside JSON config values.
