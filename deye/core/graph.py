"""Evidence graph + contradiction detection.

Builds a queryable graph over evidence already captured by
:class:`deye.core.evidence.EvidenceStore`:

    sources  --mention-->  entities
    sources  --assert--->  claims

and then flags *candidate contradictions* between claims that share a subject.

Design honesty
--------------
Contradiction detection here is **deterministic and heuristic**, not a learned
NLI model. It catches two well-defined, high-precision patterns:

  1. polarity conflict  -- two claims about the same subject where exactly one
     carries a negation cue ("not", "no longer", "denies", "failed to", ...);
  2. numeric conflict   -- two claims about the same subject + metric token that
     assert different numbers.

Every finding carries a ``confidence`` in [0, 1] and the two supporting source
URLs, so a human (or the model) can adjudicate. It is intentionally biased
toward *not* firing on weak evidence. This module is stdlib-only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from itertools import combinations

# --- lightweight text utilities ------------------------------------------------

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_ENTITY = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\b")
_NUM = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(%|percent|million|billion|bn|k|m)?", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9]+")

_NEGATION = {
    "not", "no", "never", "none", "cannot", "can't", "won't", "isn't", "aren't",
    "wasn't", "weren't", "doesn't", "don't", "didn't", "without", "denies",
    "denied", "refutes", "refuted", "false", "unable", "failed",
}
_STOP = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "was", "were", "be", "been", "being", "that", "this", "it", "as", "at",
    "by", "with", "from", "has", "have", "had", "will", "would", "its", "their",
}


def _stem(token: str) -> str:
    """Very light suffix stripper so 'increase'/'increased'/'fares'/'fare' align.

    Deliberately crude: this is a lead-finder, not a linguistics engine.
    """
    t = token
    t = t.removesuffix("'s")
    if len(t) > 5 and t.endswith("ing"):
        t = t[:-3]
    elif len(t) > 4 and t.endswith("ed") or len(t) > 4 and t.endswith("es"):
        t = t[:-2]
    elif len(t) > 3 and t.endswith("s"):
        t = t[:-1]
    if len(t) > 3 and t.endswith("e"):
        t = t[:-1]
    return t


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if t not in _STOP]


def _content_words(text: str) -> set[str]:
    return {_stem(t) for t in _tokens(text) if t not in _NEGATION}


def _has_negation(text: str) -> bool:
    toks = set(_WORD.findall(text.lower()))
    return bool(toks & _NEGATION)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _numbers(text: str) -> list[tuple[str, str]]:
    out = []
    for value, unit in _NUM.findall(text):
        out.append((value.replace(",", ""), (unit or "").lower()))
    return out


# --- graph model ---------------------------------------------------------------

@dataclass
class Claim:
    text: str
    source_url: str
    connector: str = ""
    negated: bool = False
    content: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {"text": self.text, "source_url": self.source_url,
                "connector": self.connector, "negated": self.negated}


@dataclass
class Contradiction:
    kind: str                    # "polarity" | "numeric"
    confidence: float
    subject: str
    claim_a: Claim
    claim_b: Claim
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "confidence": round(self.confidence, 3),
            "subject": self.subject,
            "detail": self.detail,
            "claim_a": self.claim_a.to_dict(),
            "claim_b": self.claim_b.to_dict(),
        }


@dataclass
class EvidenceGraph:
    entities: dict[str, list[str]] = field(default_factory=dict)   # entity -> [urls]
    claims: list[Claim] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)

    # ---- construction --------------------------------------------------------

    @classmethod
    def from_sources(cls, sources: list[dict], *, min_claim_words: int = 4) -> EvidenceGraph:
        """Build from rows shaped like EvidenceStore.query() output.

        Each row: {url, connector, title, excerpt, ...}.
        """
        g = cls()
        for row in sources:
            url = row.get("url") or ""
            connector = row.get("connector") or ""
            text = " ".join(x for x in (row.get("title"), row.get("excerpt")) if x)
            for ent in {m.strip() for m in _ENTITY.findall(text)}:
                if len(ent) >= 3:
                    g.entities.setdefault(ent, [])
                    if url and url not in g.entities[ent]:
                        g.entities[ent].append(url)
            for sent in _SENT_SPLIT.split(text):
                sent = sent.strip()
                if len(_tokens(sent)) < min_claim_words:
                    continue
                g.claims.append(Claim(
                    text=sent, source_url=url, connector=connector,
                    negated=_has_negation(sent), content=_content_words(sent),
                ))
        g.contradictions = g._detect_contradictions()
        return g

    # ---- contradiction detection --------------------------------------------

    def _detect_contradictions(
        self, *, overlap: float = 0.5, min_confidence: float = 0.5
    ) -> list[Contradiction]:
        found: list[Contradiction] = []
        for a, b in combinations(self.claims, 2):
            if a.source_url and a.source_url == b.source_url:
                continue  # same document is not a cross-source contradiction
            sim = _jaccard(a.content, b.content)
            if sim < overlap:
                continue
            shared = a.content & b.content
            subject = max(shared, key=len) if shared else "?"

            # pattern 1: exactly one side negated over otherwise-similar content
            if a.negated != b.negated:
                conf = round(0.5 + 0.5 * sim, 3)
                if conf >= min_confidence:
                    found.append(Contradiction(
                        kind="polarity", confidence=conf, subject=subject,
                        claim_a=a, claim_b=b,
                        detail="one claim negates the other over shared terms "
                               f"(overlap={sim:.2f})",
                    ))
                continue

            # pattern 2: same subject/metric, different numbers
            na, nb = _numbers(a.text), _numbers(b.text)
            if na and nb:
                units_a = {u for _, u in na}
                units_b = {u for _, u in nb}
                vals_a = {v for v, _ in na}
                vals_b = {v for v, _ in nb}
                if (units_a & units_b or ("" in units_a and "" in units_b)) and \
                        vals_a != vals_b and not (vals_a & vals_b):
                    conf = round(0.4 + 0.5 * sim, 3)
                    if conf >= min_confidence:
                        found.append(Contradiction(
                            kind="numeric", confidence=conf, subject=subject,
                            claim_a=a, claim_b=b,
                            detail=f"conflicting values {sorted(vals_a)} vs "
                                   f"{sorted(vals_b)} over shared terms",
                        ))
        found.sort(key=lambda c: c.confidence, reverse=True)
        return found

    # ---- export --------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "entities": len(self.entities),
            "claims": len(self.claims),
            "contradictions": len(self.contradictions),
        }

    def to_dict(self) -> dict:
        return {
            "summary": self.summary(),
            "entities": {k: v for k, v in sorted(self.entities.items())},
            "contradictions": [c.to_dict() for c in self.contradictions],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_markdown(self) -> str:
        s = self.summary()
        lines = [
            "# D-Eye evidence graph",
            "",
            (f"_Entities: {s['entities']} · Claims: {s['claims']} · "
            f"Candidate contradictions: {s['contradictions']}_"),
            "",
            ("> Contradiction findings are heuristic (polarity / numeric) and "
            "carry a confidence score; treat them as leads for human review."),
            "",
        ]
        if self.contradictions:
            lines.append("## Candidate contradictions")
            lines.append("")
            for i, c in enumerate(self.contradictions, 1):
                lines += [
                    (f"### [{i}] {c.kind} — confidence {c.confidence:.2f} "
                    f"(subject: {c.subject})"),
                    "",
                    f"- {c.detail}",
                    f"- A ({c.claim_a.source_url or 'n/a'}): {c.claim_a.text}",
                    f"- B ({c.claim_b.source_url or 'n/a'}): {c.claim_b.text}",
                    "",
                ]
        else:
            lines += ["_No candidate contradictions detected._", ""]
        return "\n".join(lines)


def build_graph_from_store(store, query: str = "", *, limit: int = 200) -> EvidenceGraph:
    """Convenience: build a graph from a live EvidenceStore.

    When *query* is empty, a broad wildcard pulls the most recent sources.
    """
    rows = store.query(query or "", limit=limit)
    return EvidenceGraph.from_sources(rows)
