"""Assembly + the core research workflow (the Phase-3 vertical slice).

    request -> policy -> search -> fetch -> extract -> provenance -> cited export
"""

from __future__ import annotations

from deye.connectors import (
    github_repo,
    reddit,
    rss,
    social_stub,
    v2ex,
    web_fetch,
    web_search,
    xiaoyuzhou,
    xueqiu,
    youtube,
)
from deye.core.config import Config
from deye.core.evidence import EvidenceStore
from deye.core.graph import EvidenceGraph
from deye.core.policy import ConsentPolicy
from deye.core.provenance import Envelope, ResearchPacket
from deye.core.registry import Registry
from deye.core.router import Router


def build_registry(config: Config | None = None) -> Registry:
    config = config or Config()
    reg = Registry()
    reg.register(web_fetch.manifest(config))
    for m in web_search.manifests(config):
        reg.register(m)
    reg.register(rss.manifest(config))
    reg.register(github_repo.manifest(config))
    for m in reddit.manifests(config):
        reg.register(m)
    for m in youtube.manifests(config):
        reg.register(m)
    for m in v2ex.manifests(config):
        reg.register(m)
    for m in xueqiu.manifests(config):
        reg.register(m)
    for m in xiaoyuzhou.manifests(config):
        reg.register(m)
    for m in social_stub.manifests(config):
        reg.register(m)
    return reg


def build_router(config: Config | None = None, *, allow_write: bool = False) -> Router:
    config = config or Config()
    consent = ConsentPolicy(allow_write=allow_write)
    return Router(registry=build_registry(config), consent=consent)


def search(router: Router, query: str) -> Envelope:
    return router.route("search", {"query": query})


def fetch(router: Router, url: str) -> Envelope:
    return router.route("fetch", {"url": url})


def research(router: Router, query: str, *, max_sources: int = 3,
             config: Config | None = None, persist: bool = True) -> ResearchPacket:
    """End-to-end: search, then fetch+extract the top results, into one packet.

    Deduplicates result URLs and, when *persist* is set, records the packet into
    the persistent evidence store so `query_evidence` can find it later.
    """
    config = config or Config()
    packet = ResearchPacket(query=query)
    results_env = search(router, query)
    packet.envelopes.append(results_env)

    urls: list[str] = []
    for artifact in results_env.artifacts:
        if artifact.get("type") == "search_results":
            for r in artifact["results"]:
                u = r.get("url")
                if u and u not in urls:          # dedupe
                    urls.append(u)
    for url in urls[:max_sources]:
        try:
            packet.envelopes.append(fetch(router, url))
        except Exception as exc:  # noqa: BLE001 -- record and continue
            results_env.warnings.append(f"skipped {url}: {exc}")

    if persist:
        try:
            EvidenceStore(config.evidence_db).record_packet(packet)
        except Exception as exc:  # noqa: BLE001 -- persistence is best-effort
            results_env.warnings.append(f"evidence persistence skipped: {exc}")
    return packet


def inspect_repo(router: Router, repo: str) -> Envelope:
    """Read-only GitHub repository inspection (owner/name or a github URL)."""
    return router.route("repo.inspect", {"repo": repo})


def youtube_transcript(router: Router, url: str, *, lang: str = "") -> Envelope:
    """Fetch a YouTube video's public captions via the keyless timedtext path."""
    request = {"url": url}
    if lang:
        request["lang"] = lang
    return router.route("transcript", request)


def multi_source_research(router: Router, query: str, *,
                          capabilities=("search",), max_workers: int = 4) -> dict:
    """Fan the query out across every distinct connector of the given
    capabilities, merge into one packet, and deduplicate near-duplicates."""
    from deye.research.multi_source import multi_source_search
    result = multi_source_search(router, query, capabilities=tuple(capabilities),
                                 max_workers=max_workers)
    return result.to_dict()


def evidence_graph(query: str = "", *, config: Config | None = None,
                   limit: int = 200) -> EvidenceGraph:
    """Build the entity/claim graph (with contradiction candidates) over stored evidence."""
    config = config or Config()
    store = EvidenceStore(config.evidence_db)
    rows = store.query(query or "", limit=limit)
    return EvidenceGraph.from_sources(rows)


def query_evidence(query: str, *, config: Config | None = None, limit: int = 20) -> dict:
    """Query the persistent evidence store built up by prior research runs."""
    config = config or Config()
    store = EvidenceStore(config.evidence_db)
    return {"query": query, "results": store.query(query, limit=limit), "stats": store.stats()}
