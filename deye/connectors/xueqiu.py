"""Xueqiu (雪球) read-only public HTML/JSON connector.

Xueqiu offers a public discovery page for stock symbols; anonymous
scraping is rate-limited by IP and by their standard robots UA rules.
This connector uses the public symbol page and passes through the
policy-gated `safe_get` so SSRF / size / decompression / redirect
protections apply.

Capabilities:
    ``fetch``  request: {"symbol": "SH600519"} → symbol summary HTML
"""
from __future__ import annotations

import urllib.parse

from deye.connectors.base import ConnectorError, safe_get, timed_health
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport


class XueqiuFetch:
    name = "xueqiu_fetch"
    capability = "fetch"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(
            self.name, "ok",
            "public HTML, rate-limited by Xueqiu; respects robots"
        ))

    def run(self, request: dict) -> Envelope:
        symbol = (request.get("symbol") or "").strip().upper()
        if not symbol or len(symbol) > 32:
            raise ConnectorError("xueqiu_fetch needs 'symbol' (1..32 chars)")
        # Public stock summary page
        url = f"https://xueqiu.com/S/{urllib.parse.quote(symbol)}"
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        text = body.decode("utf-8", errors="replace")
        env = Envelope(
            content=text[:20000],
            source=Source(url=final_url, connector=self.name,
                          title=f"Xueqiu: {symbol}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "xueqiu_symbol", "symbol": symbol})
        return env


def manifests(config: Config | None = None) -> list[ConnectorManifest]:
    return [
        ConnectorManifest(name="xueqiu_fetch", capability="fetch", license="MIT",
                          requires_credentials=False, cost="free", preference=45,
                          origin="public_web",
                          factory=lambda: XueqiuFetch(config)),
    ]
