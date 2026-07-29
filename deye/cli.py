"""The `deye` command-line interface.

Mirrors the MCP facade so CLI, MCP and (future) HTTP expose the same core
capabilities. Read-only by default; nothing privileged runs without a flag.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from deye import __version__
from deye.app import build_router, fetch, research, search
from deye.core.config import Config
from deye.core.redact import redact


def _print(obj) -> None:
    if isinstance(obj, str):
        print(redact(obj))
    else:
        print(redact(json.dumps(obj, indent=2, ensure_ascii=False)))


def cmd_status(args, cfg: Config) -> int:
    _print({
        "deye_version": __version__,
        "home": str(cfg.home),
        "read_only": cfg.read_only,
        "search_provider": cfg.search_provider,
    })
    return 0


def cmd_capabilities(args, cfg: Config) -> int:
    _print({"capabilities": build_router(cfg).registry.capabilities()})
    return 0


def cmd_connectors(args, cfg: Config) -> int:
    reg = build_router(cfg).registry
    _print([{
        "name": m.name, "capability": m.capability, "license": m.license,
        "requires_credentials": m.requires_credentials, "cost": m.cost,
        "preference": m.preference,
    } for m in reg.manifests])
    return 0


def cmd_doctor(args, cfg: Config) -> int:
    reports = build_router(cfg).health_all()
    ok = sum(1 for r in reports if r["status"] in ("ok", "degraded"))
    _print({"summary": f"{ok}/{len(reports)} connectors usable", "connectors": reports})
    return 0


def cmd_search(args, cfg: Config) -> int:
    env = search(build_router(cfg), args.query)
    _print(env.content)
    return 0


def cmd_fetch(args, cfg: Config) -> int:
    env = fetch(build_router(cfg), args.url)
    _print({"title": env.source.title, "url": env.source.url,
            "chars": len(env.content), "warnings": env.warnings})
    print("---")
    _print(env.content[:4000])
    return 0


def cmd_research(args, cfg: Config) -> int:
    packet = research(build_router(cfg), args.query, max_sources=args.max_sources)
    out = args.output or (cfg.ensure_home() / "last_research.md")
    Path(out).write_text(packet.to_markdown(), encoding="utf-8")
    Path(str(out) + ".json").write_text(packet.to_json(), encoding="utf-8")
    _print({"sources": len(packet.envelopes), "markdown": str(out),
            "json": str(out) + ".json"})
    return 0


def cmd_evidence(args, cfg: Config) -> int:
    from deye.app import query_evidence
    _print(query_evidence(args.query, config=cfg))
    return 0


def cmd_repo(args, cfg: Config) -> int:
    from deye.app import inspect_repo
    env = inspect_repo(build_router(cfg), args.repo)
    _print({"repo": args.repo, "warnings": env.warnings})
    print("---")
    _print(env.content)
    return 0


def cmd_graph(args, cfg: Config) -> int:
    from deye.app import evidence_graph
    g = evidence_graph(args.query or "", config=cfg)
    if args.markdown:
        out = args.output or (cfg.ensure_home() / "evidence_graph.md")
        Path(out).write_text(g.to_markdown(), encoding="utf-8")
        _print({**g.summary(), "markdown": str(out)})
    else:
        _print(g.to_dict())
    return 0


def cmd_serve_http(args, cfg: Config) -> int:
    """Remote mode: Streamable-HTTP MCP with enforced bearer auth."""
    try:
        from deye.remote import serve
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("remote mode needs extras: pip install 'deye[remote]' -- " + str(exc) + "\n")
        return 2
    return serve(host=args.host, port=args.port)


def cmd_setup(args, cfg: Config) -> int:
    home = cfg.ensure_home()
    config_path = home / "config.json"
    if not config_path.exists():
        config_path.write_text(json.dumps({
            "search_provider": cfg.search_provider,
            "read_only": True,
            "exa_api_key_ref": cfg.exa_api_key_ref,
        }, indent=2))
    _print({"message": "D-Eye set up (read-only, no credentials stored)",
            "home": str(home), "config": str(config_path)})
    return 0


def cmd_doctor_where(args, cfg: Config) -> int:
    """`deye doctor --surfaces` -- honestly report where D-Eye can be active."""
    from deye.surfaces import surface_status
    _print(surface_status())
    return 0


def cmd_init_claude(args, cfg: Config) -> int:
    """Register D-Eye with Claude Desktop (and optionally Claude Code) locally."""
    from deye.init_claude import init_claude
    report = init_claude(python_exe=args.python, dry_run=args.dry_run,
                         run_claude_code=args.run_claude_code)
    _print(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="deye", description="D-Eye capability + evidence layer")
    p.add_argument("--version", action="version", version=f"deye {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="one-time local setup (read-only, no secrets)")
    sub.add_parser("status", help="show configuration")
    sub.add_parser("capabilities", help="list capabilities")
    sub.add_parser("connectors", help="list connectors")
    d = sub.add_parser("doctor", help="health-check connectors and surfaces")
    d.add_argument("--surfaces", action="store_true", help="report Claude surface activation")

    ic = sub.add_parser("init-claude", help="register D-Eye with Claude Desktop / Claude Code")
    ic.add_argument("--python", default=None, help="python interpreter to launch the server with")
    ic.add_argument("--dry-run", action="store_true", help="show what would be written, change nothing")
    ic.add_argument("--run-claude-code", action="store_true", help="also run `claude mcp add` if the CLI is present")

    s = sub.add_parser("search", help="web search"); s.add_argument("query")
    f = sub.add_parser("fetch", help="fetch + extract a URL"); f.add_argument("url")
    r = sub.add_parser("research", help="search -> fetch -> cited packet (persists evidence)")
    r.add_argument("query")
    r.add_argument("--max-sources", type=int, default=3, dest="max_sources")
    r.add_argument("--output", "-o", default=None)

    e = sub.add_parser("evidence", help="query the persistent evidence store")
    e.add_argument("query")

    rp = sub.add_parser("repo", help="inspect a public GitHub repository (read-only)")
    rp.add_argument("repo", help="owner/name or a github.com URL")

    g = sub.add_parser("graph", help="build an evidence graph + contradiction candidates")
    g.add_argument("query", nargs="?", default="", help="filter term (blank = recent evidence)")
    g.add_argument("--markdown", action="store_true", help="write a Markdown report")
    g.add_argument("--output", "-o", default=None)

    h = sub.add_parser("serve-http", help="run the remote Streamable-HTTP MCP (needs DEYE_HTTP_TOKEN)")
    h.add_argument("--host", default="127.0.0.1")
    h.add_argument("--port", type=int, default=8080)
    return p


_DISPATCH = {
    "setup": cmd_setup, "status": cmd_status, "capabilities": cmd_capabilities,
    "connectors": cmd_connectors, "search": cmd_search, "fetch": cmd_fetch,
    "research": cmd_research, "evidence": cmd_evidence, "serve-http": cmd_serve_http,
    "init-claude": cmd_init_claude, "repo": cmd_repo, "graph": cmd_graph,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.load()
    try:
        if args.command == "doctor":
            return cmd_doctor_where(args, cfg) if args.surfaces else cmd_doctor(args, cfg)
        return _DISPATCH[args.command](args, cfg)
    except Exception as exc:  # noqa: BLE001 -- present a clean, redacted message
        sys.stderr.write("deye: " + redact(str(exc)) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
