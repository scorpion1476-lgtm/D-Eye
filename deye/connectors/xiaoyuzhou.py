"""Xiaoyuzhou (小宇宙 FM) read-only public podcast connector.

Xiaoyuzhou publishes podcast episode pages at
`https://www.xiaoyuzhoufm.com/episode/<episode_id>` — publicly
crawlable. This connector fetches an episode page through the
policy-gated `safe_get`.

Capabilities:
    ``fetch``  request: {"episode_id": "abc123"} → episode HTML
"""
from __future__ import annotations

import re

from deye.connectors.base import ConnectorError, safe_get, timed_health
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport

_ID = re.compile(r"^[A-Za-z0-9_-]{4,64}$")


class XiaoyuzhouFetch:
    name = "xiaoyuzhou_fetch"
    capability = "fetch"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(
            self.name, "ok",
            "public HTML, rate-limited; respects robots"
        ))

    def run(self, request: dict) -> Envelope:
        eid = (request.get("episode_id") or "").strip()
        if not eid or not _ID.match(eid):
            raise ConnectorError("xiaoyuzhou_fetch needs valid 'episode_id'")
        url = f"https://www.xiaoyuzhoufm.com/episode/{eid}"
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        text = body.decode("utf-8", errors="replace")
        env = Envelope(
            content=text[:20000],
            source=Source(url=final_url, connector=self.name,
                          title=f"Xiaoyuzhou episode {eid}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "xiaoyuzhou_episode", "episode_id": eid})
        return env


def manifests(config: Config | None = None) -> list[ConnectorManifest]:
    return [
        ConnectorManifest(name="xiaoyuzhou_fetch", capability="fetch", license="MIT",
                          requires_credentials=False, cost="free", preference=45,
                          origin="public_web",
                          factory=lambda: XiaoyuzhouFetch(config)),
    ]
