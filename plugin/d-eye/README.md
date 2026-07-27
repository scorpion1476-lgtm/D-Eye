# D-Eye Claude plugin

Registers the **local** D-Eye MCP server (`python -m deye.mcp_server`) and a
skill that tells the agent when to use D-Eye's search / fetch / research tools.

What this plugin does **not** do (by design, and unlike the reference plugin it
was studied from):

- no hard-coded bearer token in `.mcp.json` (uses a local stdio server);
- no SessionStart download of remote skills (supply-chain path removed);
- no PostToolUse telemetry to any remote endpoint.

Install (Claude Code):
```
claude plugin install ./plugin/d-eye
```
Then verify: `deye doctor --surfaces`.
