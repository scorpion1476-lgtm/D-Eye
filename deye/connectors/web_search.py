"""Web search. FOSS-first default; hosted providers are optional adapters."""
from __future__ import annotations

import json
import re
import urllib.parse

from deye.connectors.base import ConnectorError, safe_get, safe_post, timed_health
from deye.core.config import Config, resolve_secret
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport

_RESULT = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


def _unwrap(href: str) -> str:
    """DuckDuckGo returns `//duckduckgo.com/l/?uddg=<encoded real url>`.

    Decode the real target so downstream fetches hit the actual source (which
    is then still re-checked by the SSRF guard).
    """
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlsplit(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        qs = urllib.parse.parse_qs(parsed.query)
        target = qs.get("uddg", [""])[0]
        if target:
            return urllib.parse.unquote(target)
    return href


class DuckDuckGoSearch:
    """Keyless metasearch via the DuckDuckGo HTML endpoint (no API key)."""

    name = "search_duckduckgo"
    capability = "search"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "keyless"))

    def run(self, request: dict) -> Envelope:
        query = request["query"]
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        html = body.decode("utf-8", errors="replace")
        results = []
        for href, title in _RESULT.findall(html)[:10]:
            results.append({"title": _TAG.sub("", title).strip(), "url": _unwrap(href)})
        content = "\n".join(f"{r['title']} -- {r['url']}" for r in results) or "(no results parsed)"
        env = Envelope(
            content=content,
            source=Source(url=final_url, connector=self.name, title=f"Search: {query}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "search_results", "results": results})
        return env


class ExaSearch:
    """Optional hosted adapter for the Exa API.

    Fails closed when no key is configured: ``health()`` reports ``missing`` so
    the router transparently falls back to the keyless DuckDuckGo connector. The
    key is read from a secret *reference* at call time and is never logged.

    Supports ``mode`` in the request: ``search`` (default), ``find_similar``
    (needs ``url``), and ``answer``. Search honours ``num_results``,
    ``include_domains``, ``exclude_domains``, ``start_date``/``end_date`` and
    ``search_type`` (auto|neural|keyword|fast), and requests text + highlights.
    """

    name = "search_exa"
    capability = "search"
    is_write = False
    _BASE = "https://api.exa.ai"

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def _key(self) -> str | None:
        return resolve_secret(self.config.exa_api_key_ref)

    def health(self) -> HealthReport:
        if not self._key():
            return HealthReport(self.name, "missing",
                                "optional adapter: no EXA_API_KEY (falls back to keyless)")
        return HealthReport(self.name, "ok", "Exa API key present")

    def _payload(self, request: dict) -> tuple[str, dict]:
        mode = request.get("mode", "search")
        if mode == "find_similar":
            body = {"url": request["url"],
                    "numResults": int(request.get("num_results", 5)),
                    "contents": {"text": True, "highlights": True}}
            return "/findSimilar", body
        if mode == "answer":
            return "/answer", {"query": request["query"], "text": True}
        body: dict = {
            "query": request["query"],
            "numResults": int(request.get("num_results", 5)),
            "type": request.get("search_type", "auto"),
            "contents": {"text": {"maxCharacters": 2000}, "highlights": True},
        }
        if request.get("include_domains"):
            body["includeDomains"] = list(request["include_domains"])
        if request.get("exclude_domains"):
            body["excludeDomains"] = list(request["exclude_domains"])
        if request.get("start_date"):
            body["startPublishedDate"] = request["start_date"]
        if request.get("end_date"):
            body["endPublishedDate"] = request["end_date"]
        return "/search", body

    def run(self, request: dict) -> Envelope:
        key = self._key()
        if not key:
            raise ConnectorError("Exa adapter selected but no EXA_API_KEY configured")
        path, payload = self._payload(request)
        raw_body = json.dumps(payload).encode("utf-8")
        out, status, warnings = safe_post(
            self._BASE + path, limits=self.config.limits, body=raw_body,
            headers={"x-api-key": key, "Content-Type": "application/json",
                     "Accept": "application/json"},
        )
        if status == 401:
            raise ConnectorError("Exa API rejected the key (401)")
        if status == 429:
            warnings.append("Exa rate limit (429)")
        if status >= 400:
            raise ConnectorError(f"Exa API error status {status}")
        try:
            data = json.loads(out.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise ConnectorError(f"Exa returned non-JSON: {exc}") from exc

        results = []
        for r in (data.get("results") or []):
            results.append({
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "published": r.get("publishedDate"),
                "highlights": r.get("highlights") or [],
            })
        cost = data.get("costDollars")
        if cost:
            warnings.append(f"exa cost: ${cost.get('total', cost)}")
        answer = data.get("answer")
        content = answer if answer else (
            "\n".join(f"{x['title']} -- {x['url']}" for x in results) or "(no results)"
        )
        env = Envelope(
            content=content,
            source=Source(url=self._BASE + path, connector=self.name,
                          title=f"Exa: {request.get('query') or request.get('url','')}"),
            trust=Trust(origin="adapter", authenticated=True, untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "search_results", "provider": "exa",
                              "results": results, "cost_dollars": cost})
        return env


def manifests(config: Config | None = None) -> list[ConnectorManifest]:
    return [
        ConnectorManifest(name="search_duckduckgo", capability="search", license="MIT",
                          requires_credentials=False, cost="free", preference=10,
                          factory=lambda: DuckDuckGoSearch(config)),
        ConnectorManifest(name="search_exa", capability="search", license="proprietary-adapter",
                          requires_credentials=True, cost="metered", preference=50,
                          factory=lambda: ExaSearch(config)),
    ]
