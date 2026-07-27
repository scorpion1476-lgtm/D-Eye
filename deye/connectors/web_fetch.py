"""Fetch + extract a single web page as untrusted evidence."""
from __future__ import annotations

from deye.connectors.base import safe_get, timed_health
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport
from deye.extract import extract_title, html_to_text


class WebFetchConnector:
    name = "web_fetch"
    capability = "fetch"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "stdlib http"))

    def run(self, request: dict) -> Envelope:
        url = request["url"]
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        raw = body.decode("utf-8", errors="replace")
        text = html_to_text(raw)
        env = Envelope(
            content=text,
            source=Source(url=final_url, connector=self.name, title=extract_title(raw)),
            trust=Trust(origin="public_web", authenticated=False, untrusted=True),
            warnings=warnings,
            policy={"ssrf_checked": True, "size_limited": True},
        )
        if text:
            env.add_evidence(text[:500])
        return env


def manifest(config: Config | None = None) -> ConnectorManifest:
    return ConnectorManifest(
        name="web_fetch", capability="fetch", license="MIT",
        requires_credentials=False, preference=10,
        factory=lambda: WebFetchConnector(config),
    )
