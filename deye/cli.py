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


def cmd_usage(args, cfg: Config) -> int:
    """Report per-adapter usage, estimated cost, and call rate.

    Reads the opt-in usage log (written when DEYE_USAGE_LOG is set) under
    DEYE_HOME. Local FOSS connectors are free; paid adapters show an estimate.
    """
    from deye.backend.usage import UsageMeter
    meter = UsageMeter.from_log(cfg.home / "usage.jsonl")
    _print(meter.report())
    return 0


def cmd_semantic(args, cfg: Config) -> int:
    from deye.app import semantic_answer
    result = semantic_answer(args.query, config=cfg, k=args.k)
    _print({"query": result["query"], "corpus_size": result["corpus_size"],
            "hits": result["hits"]})
    print("---")
    _print(result["answer"]["answer"])
    return 0


def cmd_repo(args, cfg: Config) -> int:
    from deye.app import inspect_repo
    env = inspect_repo(build_router(cfg), args.repo)
    _print({"repo": args.repo, "warnings": env.warnings})
    print("---")
    _print(env.content)
    return 0


def cmd_bilibili(args, cfg: Config) -> int:
    from deye.app import bilibili_info
    env = bilibili_info(build_router(cfg), args.ref)
    art = env.artifacts[0] if env.artifacts else {}
    _print({"available": art.get("available"), "bvid": art.get("bvid"),
            "title": art.get("title"), "owner": art.get("owner"),
            "views": art.get("views"), "url": art.get("url"),
            "warnings": env.warnings})
    print("---")
    _print(env.content[:4000])
    return 0


def cmd_transcript(args, cfg: Config) -> int:
    from deye.app import youtube_transcript
    env = youtube_transcript(build_router(cfg), args.url, lang=args.lang or "")
    art = env.artifacts[0] if env.artifacts else {}
    _print({"video_id": art.get("video_id"), "lang": art.get("lang"),
            "available": art.get("available"),
            "auto_generated": art.get("auto_generated"),
            "segments": art.get("segment_count", 0), "warnings": env.warnings})
    print("---")
    _print(env.content[:4000])
    return 0


def cmd_multi_search(args, cfg: Config) -> int:
    from deye.app import multi_source_research
    out = multi_source_research(build_router(cfg), args.query,
                                capabilities=tuple(args.capabilities.split(",")))
    pkt = out["packet"]
    _print({"query": args.query, "sources": len(pkt.get("envelopes", [])),
            "errors": out["per_source_errors"],
            "dedup_clusters": len(out["dedup_clusters"])})
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


def cmd_release(args, cfg: Config) -> int:
    """`deye release <verb>`: manifest / keygen / sign / verify a bundle."""
    from pathlib import Path as _P

    from deye import release
    verb = args.verb
    if verb == "manifest":
        out = release.write_manifest(_P(args.bundle))
        _print({"manifest": str(out)}); return 0
    if verb == "keygen":
        priv, pub = release.generate_keypair(_P(args.dest))
        _print({"private_key": str(priv), "public_key": str(pub)}); return 0
    if verb == "sign":
        release.write_manifest(_P(args.bundle))
        sig = release.sign_manifest(_P(args.bundle), _P(args.key),
                                    public_key=_P(args.public) if args.public else None)
        _print({"signed": str(sig)}); return 0
    if verb == "verify":
        result = release.verify_bundle(_P(args.bundle),
                                       public_key=_P(args.public) if args.public else None)
        _print(result)
        return 0 if result["ok"] else 1
    _print({"error": f"unknown release verb: {verb}"})
    return 1


def cmd_lifecycle(args, cfg: Config) -> int:
    """Dispatch to `deye lifecycle <verb>` subcommands (env, extras, repair, status, backup, restore, portable-export, portable-import, check-update, apply-update, rollback, uninstall)."""
    from pathlib import Path as _P

    from deye import lifecycle
    verb = args.verb
    if verb == "env":
        _print(lifecycle.env_detect().to_dict()); return 0
    if verb == "extras":
        _print(lifecycle.detect_extras().to_dict()); return 0
    if verb == "repair":
        _print([s.to_dict() for s in lifecycle.repair_guidance()]); return 0
    if verb == "status":
        _print(lifecycle.aggregate_report()); return 0
    if verb == "backup":
        out = lifecycle.backup_home(_P(args.dest or (cfg.ensure_home().parent / "deye-backups")))
        _print({"backup": str(out)}); return 0
    if verb == "restore":
        _print(lifecycle.restore_home(_P(args.archive), overwrite=args.overwrite)); return 0
    if verb == "portable-export":
        out = lifecycle.portable_config_export(_P(args.dest))
        _print({"exported": str(out)}); return 0
    if verb == "portable-import":
        _print(lifecycle.portable_config_import(_P(args.src))); return 0
    if verb == "check-update":
        _print(lifecycle.check_update().to_dict()); return 0
    if verb == "apply-update":
        _print(lifecycle.apply_update(args.spec, dry_run=args.dry_run)); return 0
    if verb == "rollback":
        _print(lifecycle.rollback_to(args.version)); return 0
    if verb == "uninstall":
        _print(lifecycle.uninstall(remove_home=args.remove_home).to_dict()); return 0
    _print({"error": f"unknown lifecycle verb: {verb}"})
    return 1


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

    se = sub.add_parser("semantic", help="keyless semantic search over stored evidence (cited answer)")
    se.add_argument("query")
    se.add_argument("--k", type=int, default=5, help="how many nearest sources to ground the answer in")

    sub.add_parser("usage", help="report per-adapter usage, estimated cost, and call rate")

    rp = sub.add_parser("repo", help="inspect a public GitHub repository (read-only)")
    rp.add_argument("repo", help="owner/name or a github.com URL")

    bl = sub.add_parser("bilibili", help="fetch a Bilibili video's public info (keyless view API)")
    bl.add_argument("ref", help="a bilibili video URL, BV id, or av number")

    tr = sub.add_parser("transcript", help="fetch a YouTube video's public captions (keyless)")
    tr.add_argument("url", help="a YouTube watch URL, youtu.be link, or 11-char id")
    tr.add_argument("--lang", default=None, help="preferred caption language prefix, e.g. en")

    ms = sub.add_parser("multi-search", help="fan a query across several public connectors + dedupe")
    ms.add_argument("query")
    ms.add_argument("--capabilities", default="search",
                    help="comma-separated capabilities to fan out (default: search)")

    g = sub.add_parser("graph", help="build an evidence graph + contradiction candidates")
    g.add_argument("query", nargs="?", default="", help="filter term (blank = recent evidence)")
    g.add_argument("--markdown", action="store_true", help="write a Markdown report")
    g.add_argument("--output", "-o", default=None)

    h = sub.add_parser("serve-http", help="run the remote Streamable-HTTP MCP (needs DEYE_HTTP_TOKEN)")
    h.add_argument("--host", default="127.0.0.1")
    h.add_argument("--port", type=int, default=8080)

    rel = sub.add_parser("release", help="sign / verify a release bundle (FOSS Ed25519 + SHA256SUMS)")
    rel_sub = rel.add_subparsers(dest="verb", required=True)
    rel_m = rel_sub.add_parser("manifest", help="write SHA256SUMS for a bundle dir")
    rel_m.add_argument("bundle")
    rel_k = rel_sub.add_parser("keygen", help="generate a local Ed25519 keypair")
    rel_k.add_argument("dest")
    rel_s = rel_sub.add_parser("sign", help="write SHA256SUMS and sign it with a private key")
    rel_s.add_argument("bundle")
    rel_s.add_argument("--key", required=True, help="Ed25519 private key path")
    rel_s.add_argument("--public", default=None, help="public key to embed as PUBKEY.pem")
    rel_v = rel_sub.add_parser("verify", help="verify bundle integrity (+ signature if present)")
    rel_v.add_argument("bundle")
    rel_v.add_argument("--public", default=None, help="public key (defaults to bundle PUBKEY.pem)")

    lc = sub.add_parser("lifecycle", help="setup / update / backup / rollback / uninstall / repair")
    lc_sub = lc.add_subparsers(dest="verb", required=True)
    lc_sub.add_parser("env", help="detect OS, Python, browsers, CLIs")
    lc_sub.add_parser("extras", help="report which optional extras are available")
    lc_sub.add_parser("repair", help="actionable repair suggestions")
    lc_sub.add_parser("status", help="aggregate lifecycle report (env + extras + repair)")
    lc_b = lc_sub.add_parser("backup", help="tar.gz DEYE_HOME into dest_dir")
    lc_b.add_argument("--dest", default=None)
    lc_r = lc_sub.add_parser("restore", help="restore a home backup archive")
    lc_r.add_argument("archive")
    lc_r.add_argument("--overwrite", action="store_true")
    lc_pe = lc_sub.add_parser("portable-export", help="export a portable config file")
    lc_pe.add_argument("dest")
    lc_pi = lc_sub.add_parser("portable-import", help="import a portable config file")
    lc_pi.add_argument("src")
    lc_sub.add_parser("check-update", help="report current + available version (offline-safe)")
    lc_au = lc_sub.add_parser("apply-update", help="install a specific pip spec")
    lc_au.add_argument("spec")
    lc_au.add_argument("--dry-run", action="store_true")
    lc_rb = lc_sub.add_parser("rollback", help="reinstall a specific D-Eye version")
    lc_rb.add_argument("version")
    lc_u = lc_sub.add_parser("uninstall", help="pip-uninstall D-Eye; optionally remove DEYE_HOME (always backed up)")
    lc_u.add_argument("--remove-home", action="store_true")
    return p


_DISPATCH = {
    "setup": cmd_setup, "status": cmd_status, "capabilities": cmd_capabilities,
    "connectors": cmd_connectors, "search": cmd_search, "fetch": cmd_fetch,
    "research": cmd_research, "evidence": cmd_evidence, "semantic": cmd_semantic,
    "usage": cmd_usage, "serve-http": cmd_serve_http,
    "init-claude": cmd_init_claude, "repo": cmd_repo, "graph": cmd_graph,
    "transcript": cmd_transcript, "multi-search": cmd_multi_search,
    "bilibili": cmd_bilibili, "release": cmd_release, "lifecycle": cmd_lifecycle,
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
