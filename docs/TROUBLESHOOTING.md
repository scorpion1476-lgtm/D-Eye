# D-Eye - Troubleshooting

## Install / setup

**`deye: command not found`** - the package installed but the scripts
directory isn't on PATH. Run `./.venv/bin/deye ...` or add your
Python user-scripts dir to PATH.

**`deye setup` writes to the wrong place.** `DEYE_HOME` env var wins;
unset it or export the path you want.

**`deye doctor` says a connector is `missing`.** Run
`deye lifecycle repair` - it prints a deterministic list of
suggestions (missing extras, non-venv Python, wrong Python version).

**Python too old.** D-Eye requires Python 3.10+. Install via Homebrew,
uv, or pyenv.

## Networking

**`deye fetch URL` says `blocked by policy: DNS resolution failed`.**
Your environment probably routes outbound HTTP through a proxy that
blocks direct `socket.getaddrinfo`. D-Eye's SSRF-hardened fetch path
intentionally bypasses HTTP proxies (that IS the security posture) via
direct DNS + IP-pinned connect. Run D-Eye from an environment with
direct DNS access, or add an `HTTP_PROXY`-aware fallback connector
(not shipped in core).

**`deye fetch URL` says `blocked by policy: non-public IP`.** Working
as designed. Private IPs, loopback, link-local, cloud metadata, and
IPv4-mapped IPv6 private addresses are all rejected before any TCP
connect. If you must fetch from a private network, run D-Eye inside
that network and use its public egress.

**Reddit fetch returns 403.** Reddit's anti-bot filter rejects
low-signal User-Agents. Set an identifying UA per Reddit's guidance
in your installation.

## MCP

**Remote HTTP MCP returns `401`.** Set `DEYE_HTTP_TOKEN=<long-random-secret>`
in the server's environment before `deye serve-http`. Clients must
send `Authorization: Bearer $DEYE_HTTP_TOKEN`.

**Claude Desktop doesn't see the local MCP after `deye init-claude`.**
Restart Claude Desktop. On macOS, quit fully (Cmd-Q) before restarting.

**MCP subprocess tests hang.** Kill the child
(`pkill -f deye.mcp_server`) and rerun. If the hang persists,
`pip install -e '.[mcp]'` - the tests skip cleanly when the extra
isn't installed.

## Browser

**`invoke("browser_research", action="render_html", ...)` returns
`ok=False, reason="playwright not installed"`.**
`pip install -e '.[browser]' && playwright install chromium`.

**Browser click refused with "consent denied".** Pass a
`ConsentPolicy(allow_write=True, granted_actions={"browser.click"})`.

## Evidence store

**`deye evidence QUERY` returns nothing.**
- Check the tenant scope: the `evidence` skill defaults to
  `tenant=None` (owner scope, sees everything).
- The store uses SQL `LIKE` substring - try a partial word.
- Confirm a packet was recorded: `deye lifecycle backup --dest /tmp`
  and inspect the resulting archive.

**`invoke("evidence", action="delete", tenant="acme")` returns
`ok=False`.** Add `confirm_delete=True`. The default tenant is
protected from tenant-scoped deletion by design.

## Supply chain

**`pip-audit` fails on the editable `deye` install.** Use the wrapper:
`sh scripts/run_pip_audit.sh` - it excludes the editable install and
audits the rest against OSV.

**Licence scan reports an "unknown" licence for a new dep.** Add the
SPDX identifier to `ALLOWED_LICENCES` in `scripts/scan_licences.py`
OR the "unknown" is genuinely unknown and needs review before
shipping.

## Tests

**Live network tests skip on my machine.** This is expected in
environments that block direct DNS. Set `HTTP_PROXY=""` and
`HTTPS_PROXY=""` in the test environment, or run on a network-
permissive host.
