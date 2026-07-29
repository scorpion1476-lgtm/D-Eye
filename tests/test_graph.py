from deye.core.graph import EvidenceGraph


def test_polarity_contradiction_detected():
    sources = [
        {"url": "https://a.example/1", "connector": "web",
         "title": "Report", "excerpt": "The airline increased its fares in March."},
        {"url": "https://b.example/2", "connector": "web",
         "title": "Rebuttal", "excerpt": "The airline did not increase its fares in March."},
    ]
    g = EvidenceGraph.from_sources(sources)
    kinds = {c.kind for c in g.contradictions}
    assert "polarity" in kinds
    top = g.contradictions[0]
    assert top.claim_a.source_url != top.claim_b.source_url
    assert 0.0 < top.confidence <= 1.0


def test_numeric_contradiction_detected():
    sources = [
        {"url": "https://a.example/x", "connector": "web",
         "title": "A", "excerpt": "Quarterly revenue reached 120 million for the carrier."},
        {"url": "https://b.example/y", "connector": "web",
         "title": "B", "excerpt": "Quarterly revenue reached 90 million for the carrier."},
    ]
    g = EvidenceGraph.from_sources(sources)
    assert any(c.kind == "numeric" for c in g.contradictions)


def test_same_source_not_flagged():
    sources = [
        {"url": "https://one.example/z", "connector": "web", "title": "Same",
         "excerpt": "The system is stable. The system is not stable."},
    ]
    g = EvidenceGraph.from_sources(sources)
    # both claims share a URL -> not a cross-source contradiction
    assert g.contradictions == []


def test_agreement_not_flagged():
    sources = [
        {"url": "https://a.example/p", "connector": "web", "title": "A",
         "excerpt": "The runway reopened on Tuesday after inspection."},
        {"url": "https://b.example/q", "connector": "web", "title": "B",
         "excerpt": "The runway reopened on Tuesday after inspection completed."},
    ]
    g = EvidenceGraph.from_sources(sources)
    assert all(c.kind != "polarity" for c in g.contradictions)


def test_exports_are_serialisable():
    g = EvidenceGraph.from_sources([
        {"url": "https://a.example/1", "title": "T", "excerpt": "Boeing delivered ten jets."},
    ])
    assert "summary" in g.to_dict()
    assert g.to_json().startswith("{")
    assert "evidence graph" in g.to_markdown().lower()
