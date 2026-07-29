"""V2EX read-only connector — public JSON API, no key required.

V2EX exposes public JSON endpoints for hot / latest / show:
  https://www.v2ex.com/api/topics/hot.json
  https://www.v2ex.com/api/topics/latest.json
  https://www.v2ex.com/api/topics/show.json?id=<topic_id>

Capabilities:
    ``feed``    request: {"mode": "hot"} or {"mode": "latest"} → topic list
    ``fetch``   request: {"topic_id": 12345} → single topic + author metadata

No writes, no auth, no vote/reply.
"""
from __future__ import annotations

import json

from deye.connectors.base import ConnectorError, safe_get, timed_health
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport

_BASE = "https://www.v2ex.com/api"


class V2exFeed:
    name = "v2ex_feed"
    capability = "feed"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "public JSON API, keyless"))

    def run(self, request: dict) -> Envelope:
        mode = (request.get("mode") or "hot").lower()
        if mode not in {"hot", "latest"}:
            raise ConnectorError("v2ex mode must be 'hot' or 'latest'")
        url = f"{_BASE}/topics/{mode}.json"
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        try:
            topics = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise ConnectorError(f"v2ex returned non-JSON: {exc}") from exc
        lines: list[str] = []
        results: list[dict] = []
        for t in (topics or [])[:30]:
            title = t.get("title") or ""
            uurl = t.get("url") or ""
            node = ((t.get("node") or {}).get("title")) or ""
            lines.append(f"[{node}] {title} -- {uurl}")
            results.append({
                "title": title, "url": uurl, "node": node,
                "created": t.get("created"),
                "replies": t.get("replies"),
            })
        env = Envelope(
            content="\n".join(lines) or "(no topics)",
            source=Source(url=final_url, connector=self.name,
                          title=f"V2EX {mode} topics"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "v2ex_topics", "mode": mode, "results": results})
        return env


class V2exFetch:
    name = "v2ex_fetch"
    capability = "fetch"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "public JSON API"))

    def run(self, request: dict) -> Envelope:
        tid = request.get("topic_id") or request.get("id")
        if tid is None:
            raise ConnectorError("v2ex_fetch needs 'topic_id'")
        url = f"{_BASE}/topics/show.json?id={int(tid)}"
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise ConnectorError(f"v2ex returned non-JSON: {exc}") from exc
        if not payload:
            raise ConnectorError(f"v2ex topic {tid} not found or private")
        t = payload[0] if isinstance(payload, list) else payload
        text = "\n".join([
            f"Title: {t.get('title', '')}",
            f"Node: {((t.get('node') or {}).get('title')) or ''}",
            f"Author: {((t.get('member') or {}).get('username')) or ''}",
            f"URL: {t.get('url', '')}",
            "",
            (t.get("content") or "")[:8000],
        ])
        env = Envelope(
            content=text,
            source=Source(url=t.get("url") or final_url, connector=self.name,
                          title=f"V2EX topic {tid}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "v2ex_topic", "topic": t})
        return env


def manifests(config: Config | None = None) -> list[ConnectorManifest]:
    return [
        ConnectorManifest(name="v2ex_feed", capability="feed", license="MIT",
                          requires_credentials=False, cost="free", preference=40,
                          origin="public_web",
                          factory=lambda: V2exFeed(config)),
        ConnectorManifest(name="v2ex_fetch", capability="fetch", license="MIT",
                          requires_credentials=False, cost="free", preference=40,
                          origin="public_web",
                          factory=lambda: V2exFetch(config)),
    ]
