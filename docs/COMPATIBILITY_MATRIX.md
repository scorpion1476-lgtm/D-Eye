# D-Eye Claude surface compatibility matrix

> Honest by design. Where Anthropic does not expose a global-activation
> mechanism, this document says so. Verify each row against current Anthropic
> documentation before relying on it - surface behaviour changes over time.

| Surface | Integration mechanism | Account/global | User-wide | Per-project need | Local-device capability | One-time setup action | Auto-activation after setup | Unavoidable manual action | Verify with |
|---|---|---|---|---|---|---|---|---|---|
| Claude Code CLI | User-scope MCP server | No | Yes | None | Full | `deye setup` + add user-scope MCP entry once | Yes, all projects for the user | The one user-scope add | `claude mcp list`; `deye doctor --surfaces` |
| Claude Desktop | Local MCP server entry | No | Yes | n/a | Full (files/browser edge) | Add `deye` stdio server to Desktop MCP settings | Yes, for this install | One settings edit | Desktop > MCP servers; `deye doctor` |
| Claude Code in Desktop | Inherits Desktop/user config | No | Yes | None | Full | Same as Desktop | Yes | None beyond Desktop | `deye doctor --surfaces` |
| Claude.ai web Chat | Remote MCP custom connector | Yes (account) | Yes | May need enabling per chat | None (sandbox) | Deploy remote `deye` server; add custom connector once | Available account-wide | Possible per-chat enable | Web connector list |
| Claude Projects (web) | Remote MCP custom connector | Yes (account) | Yes | May need enabling per project | None (sandbox) | Same remote connector | Available account-wide | Possible per-project enable | Web connector list |
| Claude Cowork | Desktop/local project model | No | Yes | Follows desktop model | Full where supported | Same local MCP registration as Desktop | Follows Desktop | Confirm current availability | `deye doctor --surfaces` |
| Other MCP clients | Standard MCP (stdio/remote) | No | Yes | Client-dependent | Depends on client | Add `deye` as an MCP server | Client-dependent | Client-dependent | The client's tool list |

## The truth about "install once, use everywhere"

There is **no single switch** that enables D-Eye on every Claude surface at once,
and no honest product can claim otherwise today:

1. **Web surfaces** (Chat, Projects) reach D-Eye through a **remote MCP
   connector** and run in a sandbox that cannot touch your machine.
2. **Local surfaces** (Desktop, Code CLI, Code-in-Desktop, Cowork) reach D-Eye
   through a **local MCP server** and can use your files, terminal and browser
   edge.

These are two different mechanisms. The strongest legitimate design is:

- **one** remote connector registration -> covers web Chat + Projects account-wide;
- **one** user-scope MCP add -> covers Claude Code CLI across all projects;
- **one** Desktop MCP entry -> covers Desktop + Code-in-Desktop + Cowork.

That is three small one-time actions, after which no per-project repetition is
needed on the surfaces that support user/account scope. `deye doctor --surfaces`
reports exactly where you are active.


## Local stdio vs remote HTTP (important correction)

D-Eye ships **two distinct** MCP transports; do not conflate them:

| Mode | Transport | Reaches | Auth | Where it runs |
|---|---|---|---|---|
| **Local** | stdio (`python3 -m deye.mcp_server`) | Claude Desktop, Claude Code, Cowork (local model), other local MCP clients | OS user boundary | your machine |
| **Remote** | Streamable HTTP (`deye serve-http`, Docker) | Claude web Chat / Projects, Cowork cloud, remote MCP clients | **enforced bearer token** (401 without it) | a server you host |

The Docker image runs the **remote HTTP** service (not stdio). Claude web can
only use the remote mode. Local surfaces use the stdio mode and do **not** need
Docker. The SessionStart plugin hook is a local health check only -- it is **not**
a global activation mechanism.
