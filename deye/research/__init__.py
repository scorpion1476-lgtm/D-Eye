"""D-Eye local semantic research — FOSS-first, stdlib-first.

The `research` package provides D-Eye-native primitives for the semantic
capabilities in Category 5 of the catalogue. External providers (Exa,
Google, etc.) remain optional adapters registered as connectors; this
package works fully offline against the local `EvidenceStore` and any
supplied corpus.

Public surface:
    build_index(store)                   -> FTS5 index over stored sources
    fast_search(index, query)            -> quick keyword hits (score by BM25)
    deep_search(index, query, ...)       -> weighted keyword + phrase
    domain_filter(rows, include, exclude)
    highlights(text, query)              -> most-relevant excerpts
    find_similar(index, url)             -> shingle-based similarity
    extractive_answer(rows, query)       -> grounded answer, no LLM

Optional embedding-based capabilities live under `research.embeddings` and
`research.vector` behind the `[embeddings]` extra; they are not required
for any of the primary functions above.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

_WORD = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------------------
# 1. FTS5 index over the persistent evidence
# ---------------------------------------------------------------------------

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts USING fts5(
    url, title, excerpt, connector, content_hash, tokenize = 'porter unicode61'
);
"""


@dataclass
class SearchHit:
    url: str
    title: str
    excerpt: str
    score: float
    connector: str = ""

    def to_dict(self) -> dict:
        return {"url": self.url, "title": self.title,
                "excerpt": self.excerpt, "score": round(self.score, 4),
                "connector": self.connector}


class FTSIndex:
    """FTS5 index over evidence rows. Persistent on disk when db_path is set.

    Uses a cached connection so an in-memory index (``db_path=None``) shares
    a single ``:memory:`` database across `replace_from` and `search`.
    Without caching, every call would open a fresh, empty in-memory DB.
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path
        self._cached_conn: sqlite3.Connection | None = None

    def _conn(self) -> sqlite3.Connection:
        # For in-memory indexes, reuse a single connection so writes persist.
        if self.db_path is None:
            if self._cached_conn is None:
                self._cached_conn = sqlite3.connect(":memory:")
                self._cached_conn.row_factory = sqlite3.Row
                with self._cached_conn:
                    self._cached_conn.executescript(FTS_SCHEMA)
            return self._cached_conn
        # For on-disk indexes, a fresh connection per call is fine — the
        # data lives on disk.
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        with conn:
            conn.executescript(FTS_SCHEMA)
        return conn

    def replace_from(self, rows: list[dict]) -> int:
        """Rebuild the index from an iterable of source rows."""
        conn = self._conn()
        with conn:
            conn.execute("DELETE FROM sources_fts")
            n = 0
            for r in rows:
                conn.execute(
                    "INSERT INTO sources_fts(url, title, excerpt, connector, content_hash) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (r.get("url") or "", r.get("title") or "",
                     r.get("excerpt") or "", r.get("connector") or "",
                     r.get("content_hash") or ""),
                )
                n += 1
        if self.db_path is not None:
            conn.close()
        return n

    def _sanitise_query(self, query: str) -> str:
        # FTS5 MATCH takes a bare tokens-joined string for implicit AND. We
        # extract alphanumeric tokens (dropping punctuation the parser
        # would reject) rather than quoting, which would force exact-phrase
        # matches and defeat the porter stemmer.
        tokens = _WORD.findall((query or "").lower())
        return " ".join(tokens)


    def search(self, query: str, *, limit: int = 20) -> list[SearchHit]:
        q = self._sanitise_query(query)
        if not q:
            return []
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT url, title, excerpt, connector, "
                "  bm25(sources_fts) AS bm25_score "
                "FROM sources_fts WHERE sources_fts MATCH ? "
                "ORDER BY bm25_score LIMIT ?",
                (q, int(limit)),
            ).fetchall()
        finally:
            if self.db_path is not None:
                conn.close()
        # BM25 returns *lower is better*; invert for downstream sorting.
        out = []
        for r in rows:
            bm25 = r["bm25_score"] or 0.0
            score = 1.0 / (1.0 + max(0.0, bm25))
            out.append(SearchHit(url=r["url"], title=r["title"],
                                 excerpt=r["excerpt"], score=score,
                                 connector=r["connector"]))
        return out


def build_index(store, *, in_memory: bool = True, limit: int = 5000) -> FTSIndex:
    """Build a fresh FTS index from an EvidenceStore's most recent rows."""
    idx = FTSIndex(db_path=None if in_memory else store.db_path.with_suffix(".fts.db"))
    rows = store.query("", limit=limit)
    idx.replace_from(rows)
    return idx


# ---------------------------------------------------------------------------
# 2. Search modes
# ---------------------------------------------------------------------------

def fast_search(index: FTSIndex, query: str, *, limit: int = 5) -> list[dict]:
    return [h.to_dict() for h in index.search(query, limit=limit)]


def deep_search(index: FTSIndex, query: str, *, limit: int = 20,
                phrase_boost: float = 0.25) -> list[dict]:
    """Deep search = broader recall + a phrase-match boost.

    Runs the same FTS5 MATCH but retrieves more results and re-ranks by
    boosting rows where the whole query (as a phrase) appears in the
    excerpt or title.
    """
    hits = index.search(query, limit=limit * 4)
    phrase = (query or "").strip().lower()
    boosted: list[SearchHit] = []
    for h in hits:
        haystack = f"{h.title}\n{h.excerpt}".lower()
        bonus = phrase_boost if phrase and phrase in haystack else 0.0
        boosted.append(SearchHit(url=h.url, title=h.title, excerpt=h.excerpt,
                                 score=h.score + bonus, connector=h.connector))
    boosted.sort(key=lambda h: -h.score)
    return [h.to_dict() for h in boosted[:limit]]


# ---------------------------------------------------------------------------
# 3. Domain filters
# ---------------------------------------------------------------------------

def domain_filter(rows: list[dict], *, include: list[str] | None = None,
                  exclude: list[str] | None = None) -> list[dict]:
    """Include / exclude by registrable domain suffix."""
    import urllib.parse as up
    inc = [d.lower().lstrip(".") for d in (include or [])]
    exc = [d.lower().lstrip(".") for d in (exclude or [])]
    out: list[dict] = []
    for r in rows:
        host = (up.urlsplit(r.get("url") or "").hostname or "").lower().rstrip(".")
        if inc and not any(host == d or host.endswith("." + d) for d in inc):
            continue
        if exc and any(host == d or host.endswith("." + d) for d in exc):
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# 4. Highlights + find_similar
# ---------------------------------------------------------------------------

def highlights(text: str, query: str, *, window: int = 240,
               max_snippets: int = 3) -> list[str]:
    """Extractive highlights: return short windows around query terms."""
    hay = (text or "").strip()
    if not hay:
        return []
    terms = [t for t in _WORD.findall((query or "").lower()) if t]
    if not terms:
        return [hay[:window]]
    lower = hay.lower()
    hits: list[tuple[int, str]] = []
    for term in terms:
        start = 0
        while True:
            pos = lower.find(term, start)
            if pos < 0:
                break
            l = max(0, pos - window // 2)
            r = min(len(hay), pos + window // 2)
            hits.append((pos, hay[l:r].strip()))
            start = pos + len(term)
    # dedupe by proximity: keep hits at least `window/2` apart
    hits.sort()
    picked: list[tuple[int, str]] = []
    for pos, snippet in hits:
        if picked and abs(pos - picked[-1][0]) < window // 2:
            continue
        picked.append((pos, snippet))
        if len(picked) >= max_snippets:
            break
    return [s for _, s in picked]


def _shingles(text: str, k: int = 5) -> set[str]:
    words = _WORD.findall((text or "").lower())
    if len(words) < k:
        return {"|".join(words)} if words else set()
    return {"|".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def find_similar(rows: list[dict], url: str, *, min_score: float = 0.15,
                 limit: int = 5) -> list[dict]:
    """Shingle-based similarity between the row whose url matches *url* and
    every other row. Returns rows sorted by similarity."""
    seed = next((r for r in rows if r.get("url") == url), None)
    if seed is None:
        return []
    seed_shingles = _shingles((seed.get("excerpt") or "") + "\n" + (seed.get("title") or ""))
    scored: list[tuple[float, dict]] = []
    for r in rows:
        if r.get("url") == url:
            continue
        other = _shingles((r.get("excerpt") or "") + "\n" + (r.get("title") or ""))
        if not seed_shingles or not other:
            continue
        inter = len(seed_shingles & other)
        union = len(seed_shingles | other)
        score = inter / union if union else 0.0
        if score >= min_score:
            scored.append((score, r))
    scored.sort(key=lambda t: -t[0])
    return [{"score": round(s, 3), **r} for s, r in scored[:limit]]


# ---------------------------------------------------------------------------
# 5. Extractive, grounded answer (no LLM required)
# ---------------------------------------------------------------------------

@dataclass
class GroundedAnswer:
    query: str
    answer: str
    citations: list[dict] = field(default_factory=list)
    method: str = "extractive"          # extractive | llm_optional
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {"query": self.query, "answer": self.answer,
                "citations": list(self.citations), "method": self.method,
                "confidence": round(self.confidence, 3)}


def extractive_answer(rows: list[dict], query: str, *,
                      max_snippets: int = 3) -> GroundedAnswer:
    """Produce a grounded answer by concatenating the top highlights across
    the top-scoring rows. No LLM. No hallucination.

    Each snippet is cited with the source URL. The answer is prefixed with
    a truthful disclaimer explaining that this is an extractive result.
    """
    from deye.core.quality import score_source

    scored = sorted(rows, key=lambda r: -score_source(r).score)[:5]
    all_snippets: list[tuple[str, str]] = []  # (url, snippet)
    for r in scored:
        text = (r.get("excerpt") or "") + "\n" + (r.get("title") or "")
        for snip in highlights(text, query, max_snippets=1):
            all_snippets.append((r.get("url") or "", snip))
            if len(all_snippets) >= max_snippets:
                break
        if len(all_snippets) >= max_snippets:
            break

    if not all_snippets:
        return GroundedAnswer(
            query=query, answer="No supporting evidence found for this query in the local corpus.",
            citations=[], confidence=0.0,
        )

    lines = [f"Extractive answer for '{query}' (grounded in local evidence)."]
    citations: list[dict] = []
    for i, (url, snip) in enumerate(all_snippets, 1):
        lines.append(f"[{i}] {snip.strip()}  — <{url}>")
        citations.append({"index": i, "url": url})
    lines.append("")
    lines.append("This answer is composed of verbatim excerpts. Verify each "
                 "citation before quoting.")

    conf = min(1.0, 0.4 + 0.2 * len(all_snippets))
    return GroundedAnswer(query=query, answer="\n".join(lines),
                          citations=citations, confidence=conf)
