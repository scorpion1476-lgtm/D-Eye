"""D-Eye Source Quality Skill.

Combines the deterministic `score_source` algorithm with the
polarity+numeric contradiction detector on a set of source rows.
Every score exposes its factors + reasons so a reviewer can adjudicate.
"""
from __future__ import annotations

from typing import Any

from deye.core.graph import EvidenceGraph
from deye.core.quality import quality_report


def run(*, rows: list[dict] | None = None,
        min_confidence: float = 0.5) -> dict:
    """Score a set of source rows and detect candidate contradictions.

    Input:
        rows              - list of dicts shaped like `EvidenceStore.query()`
                            output (url, title, excerpt, content_hash, ...).
        min_confidence    - floor on contradiction confidence to include in
                            the returned findings (default 0.5).

    Output:
        {
          "quality": {"input_count", "kept_count", "clusters",
                       "top_scored", "scores_by_url"},
          "contradictions": [ ... ],
          "notes": [...]
        }

    Confidence scores are heuristic - not learned NLI. Every score comes
    with the factors that produced it so callers can adjudicate.
    """
    rows = rows or []
    qr = quality_report(rows)
    graph = EvidenceGraph.from_sources(rows)
    contradictions = [
        c.to_dict() for c in graph.contradictions
        if c.confidence >= min_confidence
    ]
    return {
        "quality": qr,
        "contradictions": contradictions,
        "notes": [
            ("Contradiction confidence scores are heuristic (polarity + "
             "numeric) - treat as leads for human review, not facts."),
            ("Every source score exposes its factors + reasons under "
             "quality.scores_by_url."),
        ],
    }


from deye.skills import Skill  # noqa: E402

SKILL = Skill(
    name="source_quality",
    version="1.0.0",
    description=("Deterministic source-quality scoring + candidate "
                 "contradiction detection (polarity + numeric). Every score "
                 "is explainable via its factor breakdown."),
    run=run,
    requires_consent=False,
    tags=("quality", "contradiction", "explainable"),
)
