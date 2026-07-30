"""D-Eye Offline Research Skill.

Operates without any network. Runs FTS5 keyword search over the
persistent evidence store, builds an extractive answer from the top
excerpts, and reports a clear degrade path when a capability would
otherwise need network.
"""
from __future__ import annotations

import os
from typing import Any

from deye.core.config import Config
from deye.core.evidence import EvidenceStore
from deye.research import build_index, deep_search, extractive_answer, fast_search


def _is_offline() -> bool:
    return os.environ.get("DEYE_OFFLINE", "").lower() in {"1", "true", "yes"}


def run(*, query: str,
        mode: str = "fast",
        limit: int = 5,
        tenant: str | None = None,
        config: Config | None = None) -> dict:
    """Run an offline research query over the local evidence store.

    Modes:
        "fast"  — BM25 top-N via the local FTS5 index.
        "deep"  — wider recall + phrase-boost re-rank.
        "answer" — build an extractive grounded answer using the top hits.

    Never touches the network. Never invents tokens.
    """
    config = config or Config.load()
    store = EvidenceStore(config.evidence_db)
    idx = build_index(store, in_memory=True, limit=5000)
    if mode == "fast":
        hits = fast_search(idx, query, limit=limit)
        return {"mode": mode, "query": query, "hits": hits,
                "offline_env": _is_offline()}
    if mode == "deep":
        hits = deep_search(idx, query, limit=limit)
        return {"mode": mode, "query": query, "hits": hits,
                "offline_env": _is_offline()}
    if mode == "answer":
        # Prefer FTS5 hits (token-aware) then fall back to the full
        # tenant-scoped corpus so extractive_answer's per-term highlight
        # finder has plenty of text to search. Store.query is a SUBSTRING
        # LIKE and misses tokenized matches when the query is a phrase.
        fts_urls = {h["url"] for h in fast_search(idx, query, limit=limit)}
        all_rows = store.query("", tenant=tenant, limit=200)
        if fts_urls:
            rows = [r for r in all_rows if r.get("url") in fts_urls] or all_rows
        else:
            rows = all_rows
        answer = extractive_answer(rows, query)
        return {"mode": mode, "query": query,
                "answer": answer.to_dict(),
                "corpus_size": len(rows),
                "offline_env": _is_offline()}
    raise ValueError(f"unknown offline mode: {mode}")


from deye.skills import Skill  # noqa: E402

SKILL = Skill(
    name="offline_research",
    version="1.0.0",
    description=("Zero-network research over local evidence: FTS5 fast/deep "
                 "search + extractive grounded answer. Honours DEYE_OFFLINE=1."),
    run=run,
    requires_consent=False,
    tags=("offline", "local", "grounded"),
)
