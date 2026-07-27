# Installing D-Eye

## Prerequisites
- Python 3.10 or newer. Check with `python3 --version`.
- Nothing else for the core. (Optional extras are opt-in.)

## Install the core (no credentials, no network dependencies)
```bash
cd deye
pip install -e .            # installs the `deye` command
deye setup                  # creates ~/.deye (owner-only), read-only mode
deye doctor                 # confirms connectors are healthy
```

## Try it
```bash
deye search "airline revenue management continuous pricing"
deye fetch "https://example.com/"
deye research "NDC distribution vs GDS" --max-sources 3 -o ./packet.md
```
`research` writes a fully cited `packet.md` plus a machine-readable `packet.md.json`.

## Optional extras
```bash
pip install -e '.[mcp]'      # real MCP stdio server (needs the mcp SDK)
pip install -e '.[secrets]'  # OS-keychain secret references
pip install -e '.[dev]'      # pytest + ruff
```

## Connect to Claude (choose the surfaces you use)

### Claude Code CLI (user-scope -> all your projects at once)
```bash
claude mcp add --scope user deye -- python3 -m deye.mcp_server
deye doctor --surfaces
```

### Claude Desktop (also covers Code-in-Desktop and Cowork)
Add to Desktop's MCP servers settings:
```json
{ "mcpServers": { "deye": { "command": "python3", "args": ["-m", "deye.mcp_server"] } } }
```

### Claude.ai web Chat / Projects (remote connector)
Web surfaces cannot reach your machine, so deploy the server somewhere reachable
(see `docker/`) and add it as a **custom connector** once. It is then available
account-wide; an individual chat/project may still need it toggled on.

### As a Claude Code plugin (bundles the local server + skill)
```bash
claude plugin install ./plugin/d-eye
```

## Remote mode (Claude web)
See `docs/REMOTE_DEPLOYMENT.md`. Local stdio cannot be reached from the web.
