"""Reddit read-only connector - public JSON, no API key required.

Uses the ``/.json`` view Reddit exposes on every listing URL. This is a
public, documented surface intended for read-only clients. We attribute
via User-Agent per Reddit's guidance and honour every rate-limit header.

Capabilities:
    ``search``  request: {"query": "...", "subreddit": "python", "limit": 10}
                          → search that subreddit (or /r/all when omitted).
    ``fetch``   request: {"url": "https://www.reddit.com/r/python/..."}
                          → fetch a specific listing/thread as JSON.

Not implemented (deliberately):
    - user account actions (writes, votes, subscriptions)
    - authenticated APIs, OAuth
    - bypass of subreddit privacy or NSFW gates
"""
from __future__ import annotations

import json
import urllib.parse

from deye.connectors.base import ConnectorError, safe_get, timed_health
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport


class RedditSearch:
    """Public read-only Reddit search via .json endpoints."""

    name = "reddit_search"
    capability = "search"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(
            lambda: HealthReport(self.name, "ok",
                                 "public /.json endpoint, keyless, rate-limited by Reddit")
        )

    def _build_url(self, request: dict) -> str:
        query = (request.get("query") or "").strip()
        if not query:
            raise ConnectorError("reddit_search needs a non-empty 'query'")
        sub = (request.get("subreddit") or "").strip()
        limit = min(int(request.get("limit", 10)), 50)
        params = {"q": query, "limit": str(limit), "restrict_sr": "on" if sub else "off"}
        base = (f"https://www.reddit.com/r/{urllib.parse.quote(sub)}/search.json"
                if sub else "https://www.reddit.com/search.json")
        return base + "?" + urllib.parse.urlencode(params)

    def run(self, request: dict) -> Envelope:
        url = self._build_url(request)
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        text = body.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConnectorError(f"reddit returned non-JSON from {url}: {exc}") from exc
        posts = []
        for child in ((data.get("data") or {}).get("children") or []):
            d = (child or {}).get("data") or {}
            posts.append({
                "title": d.get("title") or "",
                "url": ("https://www.reddit.com" + d.get("permalink"))
                        if d.get("permalink") else d.get("url") or "",
                "subreddit": d.get("subreddit_name_prefixed") or "",
                "author": d.get("author") or "",
                "score": d.get("score"),
                "num_comments": d.get("num_comments"),
                "created_utc": d.get("created_utc"),
            })
        content = "\n".join(f"[{p['subreddit']}] {p['title']} -- {p['url']}"
                            for p in posts) or "(no results)"
        env = Envelope(
            content=content,
            source=Source(url=final_url, connector=self.name,
                          title=f"Reddit search: {request.get('query')}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "reddit_search", "results": posts})
        return env


class RedditFetch:
    """Public read-only Reddit listing/thread fetcher."""

    name = "reddit_fetch"
    capability = "fetch"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "public .json"))

    def run(self, request: dict) -> Envelope:
        url = (request.get("url") or "").strip()
        if not url:
            raise ConnectorError("reddit_fetch needs 'url'")
        if not urllib.parse.urlsplit(url).netloc.endswith("reddit.com"):
            raise ConnectorError("reddit_fetch is only for reddit.com URLs")
        # Reddit URLs return HTML by default; the .json variant returns JSON.
        # Insert /.json before the query string if missing.
        parts = urllib.parse.urlsplit(url)
        path = parts.path if parts.path.rstrip("/").endswith(".json") else parts.path.rstrip("/") + ".json"
        json_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
        body, final_url, warnings = safe_get(json_url, limits=self.config.limits)
        text = body.decode("utf-8", errors="replace")
        env = Envelope(
            content=text[:20000],
            source=Source(url=final_url, connector=self.name,
                          title=f"Reddit fetch: {url}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        return env


def manifests(config: Config | None = None) -> list[ConnectorManifest]:
    return [
        ConnectorManifest(name="reddit_search", capability="search", license="MIT",
                          requires_credentials=False, cost="free", preference=40,
                          origin="public_web",
                          factory=lambda: RedditSearch(config)),
        ConnectorManifest(name="reddit_fetch", capability="fetch", license="MIT",
                          requires_credentials=False, cost="free", preference=40,
                          origin="public_web",
                          factory=lambda: RedditFetch(config)),
    ]
