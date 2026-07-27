"""Remote mode: a genuine Streamable-HTTP MCP service with enforced auth.

This is what Claude web / Cowork and other cloud MCP clients can reach -- unlike
the local stdio server, which they cannot. Auth is enforced IN-PROCESS here (not
merely delegated to a proxy): every request to the MCP path must carry
``Authorization: Bearer <DEYE_HTTP_TOKEN>``. ``/healthz`` is intentionally open
for load-balancer probes.

TLS termination and additional rate limiting should still sit at a reverse proxy
in production (see docs/REMOTE_DEPLOYMENT.md); this module makes the auth real so
the service is not open-by-default if the proxy is misconfigured.
"""

from __future__ import annotations

import os
import sys

from deye.mcp_server import build_fastmcp


def _require_token() -> str:
    token = os.environ.get("DEYE_HTTP_TOKEN", "")
    if not token or len(token) < 16:
        sys.stderr.write(
            "DEYE_HTTP_TOKEN is unset or too short (>=16 chars required). "
            "Refusing to start an unauthenticated remote MCP service.\n"
        )
        raise SystemExit(2)
    return token


def build_app(token: str | None = None):
    """Return the Starlette ASGI app with bearer-auth middleware. Importable for tests."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse, PlainTextResponse
    from starlette.routing import Route

    token = token or _require_token()
    server = build_fastmcp()
    app = server.streamable_http_app()

    class BearerAuth(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path == "/healthz":
                return await call_next(request)
            auth = request.headers.get("authorization", "")
            if not auth.startswith("Bearer ") or auth[7:] != token:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    app.add_middleware(BearerAuth)
    app.router.routes.append(
        Route("/healthz", lambda r: PlainTextResponse("ok"), methods=["GET"])
    )
    return app


def serve(host: str = "127.0.0.1", port: int = 8080) -> int:
    import uvicorn
    token = _require_token()
    app = build_app(token)
    sys.stderr.write(f"D-Eye remote MCP (streamable-http) on {host}:{port} -- auth REQUIRED\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0
