# D-Eye remote deployment (for Claude web / Cowork)

Local stdio MCP is not reachable from Claude web. To use D-Eye there you run the
**remote** Streamable-HTTP MCP service and register it as a custom connector.

## What the service enforces (verified)
- Refuses to start without `DEYE_HTTP_TOKEN` (>= 16 chars) -- no open-by-default.
- Every `/mcp` request requires `Authorization: Bearer <DEYE_HTTP_TOKEN>`
  (unauthenticated and wrong-token requests get HTTP 401).
- `/healthz` is open for load-balancer probes only.

## Run it
```bash
export DEYE_HTTP_TOKEN="$(openssl rand -hex 24)"   # store in a secret manager
deye serve-http --host 0.0.0.0 --port 8080
# or:
DEYE_HTTP_TOKEN=... docker compose -f docker/docker-compose.yml up --build
```

## Put this in front (production)
- **TLS**: terminate HTTPS at a reverse proxy (Caddy/nginx/Traefik). Example
  (Caddy): `deye.example.com { reverse_proxy 127.0.0.1:8080 }`.
- **Rate limiting + request size**: enforce at the proxy (e.g. nginx
  `limit_req` and `client_max_body_size`).
- **Network**: bind the app to loopback and expose only via the proxy.
- **Logs**: D-Eye redacts secrets in its own output; ensure proxy logs do not
  capture the Authorization header.

## Register in Claude web
Add a custom connector pointing at `https://deye.example.com/mcp` with the bearer
token. It becomes available at the account level; an individual chat/project may
still need it enabled.

## Rollback
`docker compose down` (stateless service). No migrations. Rotate the token by
changing `DEYE_HTTP_TOKEN` and restarting.

## Honestly not yet done
Per-tenant isolation and per-client quotas are single-token/single-tenant in this
release. For multi-tenant use, run one instance per tenant behind the proxy, or
wait for the roadmap multi-tenant build. Verified here: start/refusal, auth 401s,
health. NOT verified here: a live end-to-end handshake from the Claude web client
(requires the hosted deployment).
