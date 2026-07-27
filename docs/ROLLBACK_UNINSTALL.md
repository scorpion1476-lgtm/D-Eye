# Rolling back and uninstalling D-Eye

D-Eye is intentionally low-footprint: a Python package, a `~/.deye` directory,
and whatever MCP entries you added yourself. Nothing runs as root; no system
services are installed.

## Remove Claude integrations
- **Claude Code CLI:** `claude mcp remove deye`
- **Claude Desktop / Cowork:** delete the `deye` entry from MCP settings.
- **Web connector:** remove the custom connector in the web UI.
- **Plugin:** `claude plugin uninstall d-eye`

## Uninstall the package
```bash
pip uninstall deye
```

## Remove local data (config + exported packets)
```bash
rm -rf ~/.deye        # or $DEYE_HOME if you set it
```

## Rollback to a previous version
Because the core has no third-party runtime dependencies, rollback is just
re-installing the version you want:
```bash
pip install -e .      # from a checkout at the desired revision
```
There are no database migrations to reverse in this slice; exported research
packets are plain files you can keep or delete freely.
