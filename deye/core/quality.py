"""Evidence quality primitives — deterministic, stdlib-only.

Complements `deye/core/graph.py` (contradiction detection) with:

* `score_source(...)`   — deterministic source-quality score in [0, 1]
* `deduplicate(rows)`   — normalise + hash-cluster near-duplicate rows
* `change_monitor(...)` — schedule/report re-check candidates from an
  `EvidenceStore` based on `changed_since`

Everything is heuristic, high-precision, and audit-friendly: no ML, no
external services, no learned weights. Designed so a reviewer can eyeball
why a score / dedup decision was made.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone

_WORD = re.compile(r"[a-z0-9]+")

# Trusted-source lists — extended by callers via `trusted_domains=...`.
# Kept intentionally small and neutral; project-specific lists belong in
# config.
DEFAULT_TRUSTED_DOMAINS: frozenset[str] = frozenset({
    "arxiv.org", "acm.org", "ieee.org",
    "wikipedia.org", "wikimedia.org",
    "python.org", "docs.python.org",
    "github.com",
    "who.int", "cdc.gov", "nih.gov", "europa.eu",
    "reuters.com", "apnews.com", "bbc.co.uk", "bbc.com",
    "nist.gov", "iso.org",
})

# Low-signal / commonly aggregator hosts get a small penalty (not banned).
DEFAULT_AGGREGATOR_DOMAINS: frozenset[str] = frozenset({
    "medium.com", "substack.com", "tumblr.com", "quora.com", "wordpress.com",
    "blogspot.com",
})


# ---------------------------------------------------------------------------
# 1. Source quality scoring
# ---------------------------------------------------------------------------

@dataclass
class QualityScore:
    url: str
    score: float                    # [0.0, 1.0]
    factors: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"url": self.url, "score": round(self.score, 3),
                "factors": {k: round(v, 3) for k, v in self.factors.items()},
                "reasons": list(self.reasons)}


def _host_for(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower().rstrip(".")
    except (TypeError, ValueError):
        return ""


def score_source(row: dict, *,
                 trusted_domains: set[str] | None = None,
                 aggregator_domains: set[str] | None = None) -> QualityScore:
    """Score a source dict shaped like an EvidenceStore.query() row.

    Factors:
      + 0.3  trusted registrable domain
      - 0.1  aggregator domain (blogspot/medium/etc.)
      + 0.15 https scheme
      + 0.10 title present + non-empty
      + 0.10 excerpt >= 200 characters
      + 0.05 content_hash present (evidence integrity)
      + 0.10 retrieved_at within the last 365 days (freshness)
      + 0.05 URL depth ≤ 4 (canonical-looking source)
    """
    trusted = frozenset(d.lower() for d in (trusted_domains or DEFAULT_TRUSTED_DOMAINS))
    aggregators = frozenset(d.lower() for d in (aggregator_domains or DEFAULT_AGGREGATOR_DOMAINS))
    url = (row.get("url") or "").strip()
    host = _host_for(url)
    scheme = urllib.parse.urlsplit(url).scheme.lower() if url else ""
    path = urllib.parse.urlsplit(url).path if url else ""
    title = (row.get("title") or "").strip()
    excerpt = (row.get("excerpt") or "").strip()
    content_hash = (row.get("content_hash") or "").strip()

    factors: dict[str, float] = {}
    reasons: list[str] = []

    if host and any(host == d or host.endswith("." + d) for d in trusted):
        factors["trusted_domain"] = 0.30
        reasons.append(f"trusted domain match: {host}")
    if host and any(host == d or host.endswith("." + d) for d in aggregators):
        factors["aggregator_penalty"] = -0.10
        reasons.append(f"aggregator domain penalty: {host}")
    if scheme == "https":
        factors["https"] = 0.15
    elif scheme:
        reasons.append(f"non-https scheme: {scheme}")
    if title:
        factors["has_title"] = 0.10
    if len(excerpt) >= 200:
        factors["excerpt_length"] = 0.10
    if content_hash:
        factors["has_hash"] = 0.05

    retrieved_at = row.get("retrieved_at")
    if isinstance(retrieved_at, str):
        try:
            dt = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - dt).days
            if 0 <= age_days <= 365:
                factors["fresh"] = 0.10
        except ValueError:
            pass

    depth = len([p for p in path.split("/") if p])
    if 0 < depth <= 4:
        factors["canonical_depth"] = 0.05

    raw = sum(factors.values())
    # Clip to [0, 1]
    score = max(0.0, min(1.0, raw))
    return QualityScore(url=url, score=score, factors=factors, reasons=reasons)


def score_all(rows: list[dict], **kwargs) -> list[QualityScore]:
    return [score_source(r, **kwargs) for r in rows]


# ---------------------------------------------------------------------------
# 2. Duplicate removal
# ---------------------------------------------------------------------------

def _normalise_url(url: str) -> str:
    """Canonicalise a URL for dedup: lowercase host, drop fragments, sort
    query params, strip tracking params, strip trailing slash from path.
    """
    if not url:
        return ""
    try:
        parts = urllib.parse.urlsplit(url)
    except (TypeError, ValueError):
        return url
    host = (parts.hostname or "").lower()
    if parts.port:
        host = f"{host}:{parts.port}"
    tracking = {
        "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
        "gclid", "fbclid", "yclid", "mc_cid", "mc_eid", "ref", "ref_src",
        "src", "srsltid",
    }
    qs = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
          if k.lower() not in tracking]
    qs.sort()
    query = urllib.parse.urlencode(qs, doseq=True)
    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return urllib.parse.urlunsplit((parts.scheme.lower(), host, path, query, ""))


def _shingles(text: str, k: int = 5) -> set[str]:
    words = _WORD.findall((text or "").lower())
    if len(words) < k:
        return {"|".join(words)} if words else set()
    return {"|".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class DedupeCluster:
    canonical_url: str
    urls: list[str]
    reason: str            # "exact_url" | "content_hash" | "shingle_overlap"

    def to_dict(self) -> dict:
        return {"canonical_url": self.canonical_url, "urls": list(self.urls),
                "reason": self.reason}


def deduplicate(rows: list[dict], *, shingle_threshold: float = 0.85) -> tuple[list[dict], list[DedupeCluster]]:
    """Return (kept_rows, clusters).

    Strategy:
        1. group by normalised URL (canonical exact-dup);
        2. group by content_hash across the survivors;
        3. group by shingle overlap ≥ threshold.

    A row without url + content_hash + excerpt is kept unchanged.
    """
    if not rows:
        return [], []
    kept: list[dict] = []
    clusters: list[DedupeCluster] = []

    # 1. by normalised URL
    by_norm: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        n = _normalise_url(r.get("url") or "")
        if n:
            by_norm.setdefault(n, []).append(i)

    represented: set[int] = set()
    for n, idxs in by_norm.items():
        if len(idxs) > 1:
            urls = [rows[i].get("url") or "" for i in idxs]
            clusters.append(DedupeCluster(canonical_url=urls[0], urls=urls,
                                          reason="exact_url"))
            represented.update(idxs[1:])

    # 2. by content_hash across survivors
    survivors = [i for i in range(len(rows)) if i not in represented]
    by_hash: dict[str, list[int]] = {}
    for i in survivors:
        h = (rows[i].get("content_hash") or "").strip()
        if h:
            by_hash.setdefault(h, []).append(i)
    for h, idxs in by_hash.items():
        if len(idxs) > 1:
            urls = [rows[i].get("url") or "" for i in idxs]
            clusters.append(DedupeCluster(canonical_url=urls[0], urls=urls,
                                          reason="content_hash"))
            represented.update(idxs[1:])

    # 3. by shingle overlap across survivors
    survivors2 = [i for i in range(len(rows)) if i not in represented]
    shingles = {i: _shingles(rows[i].get("excerpt") or "") for i in survivors2}
    used: set[int] = set()
    for i in survivors2:
        if i in used:
            continue
        cluster = [i]
        for j in survivors2:
            if j <= i or j in used:
                continue
            if _jaccard(shingles[i], shingles[j]) >= shingle_threshold:
                cluster.append(j)
        if len(cluster) > 1:
            urls = [rows[c].get("url") or "" for c in cluster]
            clusters.append(DedupeCluster(canonical_url=urls[0], urls=urls,
                                          reason="shingle_overlap"))
            used.update(cluster[1:])
            represented.update(cluster[1:])

    for i, r in enumerate(rows):
        if i not in represented:
            kept.append(r)
    return kept, clusters


# ---------------------------------------------------------------------------
# 3. Change monitoring
# ---------------------------------------------------------------------------

@dataclass
class ChangeReport:
    url: str
    changed: bool
    latest_hash: str | None
    previous_hash: str | None
    detail: str = ""

    def to_dict(self) -> dict:
        return {"url": self.url, "changed": self.changed,
                "latest_hash": self.latest_hash,
                "previous_hash": self.previous_hash, "detail": self.detail}


def change_monitor(store, urls: list[str]) -> list[ChangeReport]:
    """Report which of *urls* have a different hash than their most recent
    prior record in the given `EvidenceStore`.

    Uses the built-in `EvidenceStore.changed_since(url)` (already tested;
    kept identical in semantics — this function just batches).
    """
    out: list[ChangeReport] = []
    for u in urls:
        row = store.changed_since(u)
        if row is None:
            out.append(ChangeReport(url=u, changed=False, latest_hash=None,
                                    previous_hash=None,
                                    detail="fewer than 2 recorded snapshots"))
            continue
        out.append(ChangeReport(
            url=u, changed=bool(row["changed"]),
            latest_hash=row.get("latest"), previous_hash=row.get("previous"),
            detail="latest differs from previous" if row["changed"]
                   else "no change",
        ))
    return out


# ---------------------------------------------------------------------------
# Convenience for the CLI / MCP tool
# ---------------------------------------------------------------------------

def quality_report(rows: list[dict], **kwargs) -> dict:
    """One-shot: score every row, dedup, return a summary."""
    scores = [s.to_dict() for s in score_all(rows, **kwargs)]
    kept, clusters = deduplicate(rows)
    scores_by_url = {s["url"]: s for s in scores}
    return {
        "input_count": len(rows),
        "kept_count": len(kept),
        "clusters": [c.to_dict() for c in clusters],
        "top_scored": sorted(scores, key=lambda s: -s["score"])[:10],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scores_by_url": scores_by_url,
    }
