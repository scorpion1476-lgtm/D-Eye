# D-Eye - Quickstart

_Ten minutes from clean machine to first cited research packet._

## 1. Prerequisites

- **Python 3.10 or newer.**
- **git** (only if you plan to publish back to a repository).
- **Optional:** Docker for the containerised remote MCP.

That is the entire prerequisite list. No API keys, no vendor accounts,
no cloud services. The core install pulls **zero runtime dependencies**.

## 2. Clean-machine install

```bash
# Clone
git clone https://github.com/scorpion1476-lgtm/D-Eye D-Eye
cd D-Eye/repository/deye

# Isolated venv
python3 -m venv .venv
./.venv/bin/python -m pip install -e .

# First-time setup
./.venv/bin/deye setup           # writes ~/.deye/config.json
./.venv/bin/deye doctor          # confirms connector health
```

`~/.deye/` now contains your config + persistent evidence database.
Nothing was written outside your home directory or the checkout.

## 3. First research packet

```bash
./.venv/bin/deye research \
    "continuous pricing airline revenue management" \
    --max-sources 3 \
    --output packet.md
```

Result: `packet.md` (fully cited) + `packet.md.json` (machine-readable)
+ 4 rows inserted into `~/.deye/evidence.db` (1 packet + 3 sources).

## 4. Query the evidence you just captured

```bash
./.venv/bin/deye evidence "continuous pricing"
```

Returns a JSON list of matching rows with URL, connector, retrieved-at
timestamp, content hash, and excerpt.

## 5. Enable optional extras (only what you need)

```bash
./.venv/bin/python -m pip install -e '.[mcp]'      # local stdio MCP server
./.venv/bin/python -m pip install -e '.[remote]'   # remote HTTP MCP + bearer auth
./.venv/bin/python -m pip install -e '.[browser]'  # optional Playwright adapter
./.venv/bin/python -m pip install -e '.[secrets]'  # OS keyring
./.venv/bin/python -m pip install -e '.[rich]'     # richer HTTP/RSS
```

Each extras group is documented in `docs/DEPENDENCY_AND_LICENCE_POLICY.md`
with SPDX licence, purpose, and replacement path.

## 6. Register with Claude Desktop / Claude Code

```bash
./.venv/bin/deye init-claude --dry-run   # preview the config write
./.venv/bin/deye init-claude             # actually write the config
```

Restart Claude Desktop after registration. See [`CLAUDE_SURFACE_SUPPORT.md`](CLAUDE_SURFACE_SUPPORT.md)
for what happens on each Claude surface.

## 7. Zero-network mode

```bash
DEYE_OFFLINE=1 ./.venv/bin/deye evidence "continuous pricing"
```

Details in [`OFFLINE_MODE.md`](OFFLINE_MODE.md).

## 8. Verify everything is healthy

```bash
./.venv/bin/deye doctor
./.venv/bin/deye lifecycle env
./.venv/bin/deye lifecycle repair
```

## Where to next

- [`USER_GUIDE.md`](USER_GUIDE.md) - end-user command tour.
- [`CLI_GUIDE.md`](CLI_GUIDE.md) - every CLI subcommand + flag.
- [`MCP_GUIDE.md`](MCP_GUIDE.md) - local + remote MCP deployment.
- [`SKILLS_GUIDE.md`](SKILLS_GUIDE.md) - the 8 D-Eye skills.
- [`CONNECTOR_GUIDE.md`](CONNECTOR_GUIDE.md) - using + writing connectors.
- [`BROWSER_RESEARCH_GUIDE.md`](BROWSER_RESEARCH_GUIDE.md) - optional browser adapter.
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) - common issues + fixes.
- [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) - extend D-Eye.
