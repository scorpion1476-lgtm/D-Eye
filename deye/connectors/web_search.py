"""Web search. FOSS-first default; hosted providers are optional adapters."""
from __future__ import annotations

import re
import urllib.parse

from deye.connectors.base import safe_get, timed_health
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
    """Optional hosted adapter. Fails closed with no key -- never a hard dependency."""

    name = "search_exa"
    capability = "search"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        key = resolve_secret(self.config.exa_api_key_ref)
        if not key:
            return HealthReport(self.name, "missing", "optional adapter, UNIMPLEMENTED (no EXA_API_KEY)")
        return HealthReport(self.name, "degraded", "key present but adapter is a stub (unimplemented)")

    def run(self, request: dict) -> Envelope:  # pragma: no cover - unimplemented stub
        raise NotImplementedError(
            "Exa adapter is intentionally unimplemented in this release; "
            "it is advertised as an optional integration only."
        )


def manifests(config: Config | None = None) -> list[ConnectorManifest]:
    return [
        ConnectorManifest(name="search_duckduckgo", capability="search", license="MIT",
                          requires_credentials=False, cost="free", preference=10,
                          factory=lambda: DuckDuckGoSearch(config)),
        ConnectorManifest(name="search_exa", capability="search", license="proprietary-adapter",
                          requires_credentials=True, cost="metered", preference=50,
                          factory=lambda: ExaSearch(config)),
    ]
