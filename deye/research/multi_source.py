"""Multi-source social + community research orchestrator.

Uses the D-Eye router to run the same query across several public
connectors in parallel (or sequentially in the deterministic path),
merges the resulting envelopes into one `ResearchPacket`, and applies
`deye.core.quality.deduplicate` to remove near-duplicates.

Category 3 row: C03-F015. Uses only local FOSS routing + existing
connectors; no new external dependency.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable

from deye.core.quality import deduplicate
from deye.core.provenance import ResearchPacket


@dataclass
class MultiSourceResult:
    packet: ResearchPacket
    per_source_errors: dict[str, str]
    dedup_clusters: list[dict]

    def to_dict(self) -> dict:
        return {
            "packet": self.packet.to_dict(),
            "per_source_errors": dict(self.per_source_errors),
            "dedup_clusters": list(self.dedup_clusters),
        }


def multi_source_search(router, query: str, *,
                        capabilities: Iterable[str] = ("search", "feed"),
                        max_workers: int = 4) -> MultiSourceResult:
    """Fan-out the query across every connector that implements one of
    the requested capabilities, then merge + deduplicate.

    - `router` is a `deye.core.router.Router` instance.
    - `capabilities` picks which connector protocols to invoke.
    - Errors from individual connectors are captured (not raised) so
      one bad source does not kill the aggregate.
    """
    # Enumerate candidate connectors per capability
    candidates: list[tuple[str, str]] = []
    for cap in capabilities:
        for mf in router.registry.for_capability(cap):
            if mf.factory is None:
                continue
            candidates.append((mf.name, cap))

    packet = ResearchPacket(query=query)
    errors: dict[str, str] = {}

    def _one(name: str, cap: str):
        try:
            # Route to THIS specific connector by name. Routing by capability
            # alone would collapse every candidate onto the single top-
            # preference connector, so the fan-out would query one source N
            # times instead of N distinct sources.
            env = router.route_named(name, {"query": query})
            return name, env, None
        except Exception as exc:  # noqa: BLE001 -- record + continue
            return name, None, str(exc)

    if max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(_one, n, c): n for n, c in candidates}
            for fut in as_completed(futures):
                name, env, err = fut.result()
                if env is not None:
                    packet.envelopes.append(env)
                else:
                    errors[name] = err
    else:
        for n, c in candidates:
            name, env, err = _one(n, c)
            if env is not None:
                packet.envelopes.append(env)
            else:
                errors[name] = err

    # Build (url, connector, title, excerpt, content_hash) rows for dedup.
    from deye.core.provenance import content_hash
    dedup_input = [
        {"url": e.source.url, "connector": e.source.connector,
         "title": e.source.title, "excerpt": (e.content or "")[:500],
         "content_hash": content_hash(e.content)}
        for e in packet.envelopes
    ]
    _kept, clusters = deduplicate(dedup_input)
    return MultiSourceResult(
        packet=packet,
        per_source_errors=errors,
        dedup_clusters=[c.to_dict() for c in clusters],
    )
