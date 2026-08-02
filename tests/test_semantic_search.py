"""C05-F002 keyless semantic search: local embeddings + local vector index.

Acceptance: with NO API key and NO network, the default embedder produces a
deterministic, normalised vector; the local vector index ranks semantically
related sources above unrelated ones (beyond exact keyword match); and the
semantic answer is grounded in the retrieved sources with per-source citations.
"""
from __future__ import annotations

import math

import pytest

from deye.research import semantic_answer, semantic_search
from deye.research.embeddings import (
    HashingEmbedder,
    cosine,
    default_embedder,
    load_embedder,
)
from deye.research.vector import VectorIndex

CORPUS = [
    {"url": "u1", "title": "Airline revenue management",
     "excerpt": "continuous pricing and fare optimization for airlines"},
    {"url": "u2", "title": "Sourdough bread baking",
     "excerpt": "starter hydration, oven temperature, and crumb structure"},
    {"url": "u3", "title": "Airfare dynamic pricing",
     "excerpt": "dynamic pricing of air tickets and airline seat inventory"},
]


# -- embedder ---------------------------------------------------------------

def test_default_embedder_is_keyless_hashing():
    assert isinstance(default_embedder(), HashingEmbedder)


def test_embedding_is_deterministic_and_normalised():
    emb = HashingEmbedder(dim=256)
    v1 = emb.embed("airline revenue management")
    v2 = emb.embed("airline revenue management")
    assert v1 == v2                       # deterministic across calls
    assert len(v1) == 256
    assert abs(math.sqrt(sum(x * x for x in v1)) - 1.0) < 1e-9   # unit length


def test_subword_recall_beats_unrelated():
    emb = HashingEmbedder()
    # "airline"/"airlines" share char 3-grams; "bicycle" shares none.
    sim_related = cosine(emb.embed("airline"), emb.embed("airlines"))
    sim_unrelated = cosine(emb.embed("airline"), emb.embed("bicycle"))
    assert sim_related > 0.3
    assert sim_related > sim_unrelated


def test_neural_extra_is_optional_not_required():
    # The keyless default must not require the heavy extra; asking for it
    # explicitly raises a clear error when the extra is absent.
    with pytest.raises(RuntimeError):
        load_embedder("neural")


# -- vector index -----------------------------------------------------------

def test_vector_index_returns_nearest_neighbour():
    emb = HashingEmbedder()
    idx = VectorIndex(dim=emb.dim).build(emb, CORPUS)
    assert len(idx) == 3
    hits = idx.search_text(emb, "airline pricing", k=3)
    # top hit is an airline doc, not the bread doc
    assert hits[0][1]["url"] in {"u1", "u3"}
    bread = next(score for score, p in hits if p["url"] == "u2")
    top = hits[0][0]
    assert top > bread


def test_vector_index_save_load_roundtrip(tmp_path):
    emb = HashingEmbedder()
    idx = VectorIndex(dim=emb.dim).build(emb, CORPUS)
    path = idx.save(tmp_path / "vec.json")
    reloaded = VectorIndex.load(path)
    assert len(reloaded) == len(idx)
    a = idx.search_text(emb, "airline pricing", k=3)
    b = reloaded.search_text(emb, "airline pricing", k=3)
    assert [p["url"] for _, p in a] == [p["url"] for _, p in b]


# -- high-level semantic search + cited answer ------------------------------

def test_semantic_search_ranks_relevant_above_irrelevant():
    hits = semantic_search(CORPUS, "airline pricing", k=3)
    assert hits[0]["url"] in {"u1", "u3"}
    scores = {h["url"]: h["semantic_score"] for h in hits}
    # The unrelated bread doc ranks last and is far below the top airline doc
    # (a tiny nonzero cosine is an expected hashing-collision artifact).
    assert scores["u2"] == min(scores.values())
    assert scores["u2"] < 0.1
    assert scores["u2"] < scores[hits[0]["url"]] / 3


def test_semantic_answer_is_grounded_and_cited():
    ans = semantic_answer(CORPUS, "airline pricing", k=2)
    assert ans.method == "semantic_extractive"
    assert ans.citations                              # at least one citation
    cited_urls = {c["url"] for c in ans.citations}
    assert cited_urls <= {"u1", "u3"}                 # only airline sources cited
    assert "u2" not in cited_urls


def test_app_semantic_answer_over_evidence_store(tmp_path, monkeypatch):
    monkeypatch.setenv("DEYE_HOME", str(tmp_path))
    from deye.core.config import Config
    from deye.core.evidence import EvidenceStore
    from deye.core.provenance import Envelope, ResearchPacket, Source

    cfg = Config.load()
    store = EvidenceStore(cfg.evidence_db)
    packet = ResearchPacket(query="seed")
    for row in CORPUS:
        packet.envelopes.append(Envelope(
            content=row["excerpt"],
            source=Source(url=row["url"], connector="test", title=row["title"])))
    store.record_packet(packet)

    from deye.app import semantic_answer as app_semantic_answer
    result = app_semantic_answer("airline pricing", config=cfg, k=2)
    assert result["corpus_size"] == 3
    assert result["hits"][0]["url"] in {"u1", "u3"}
    assert result["answer"]["citations"]
