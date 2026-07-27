"""RSS/Atom feed reader (stdlib XML; feedparser used if installed)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from deye.connectors.base import safe_get, timed_health
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport


class RSSConnector:
    name = "rss"
    capability = "feed"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "stdlib xml"))

    def run(self, request: dict) -> Envelope:
        url = request["url"]
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        items = []
        try:
            root = ET.fromstring(body)
            for node in root.iter():
                tag = node.tag.split("}")[-1].lower()
                if tag in ("item", "entry"):
                    title = _child_text(node, "title")
                    link = _child_text(node, "link") or _child_attr(node, "link", "href")
                    items.append({"title": title, "url": link})
        except ET.ParseError as exc:
            warnings.append(f"feed parse error: {exc}")
        content = "\n".join(f"{i['title']} -- {i['url']}" for i in items[:25]) or "(no items)"
        env = Envelope(
            content=content,
            source=Source(url=final_url, connector=self.name, title="RSS feed"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "feed_items", "items": items[:25]})
        return env


def _child_text(node, name):
    for c in node:
        if c.tag.split("}")[-1].lower() == name and c.text:
            return c.text.strip()
    return ""


def _child_attr(node, name, attr):
    for c in node:
        if c.tag.split("}")[-1].lower() == name:
            return c.attrib.get(attr, "")
    return ""


def manifest(config: Config | None = None) -> ConnectorManifest:
    return ConnectorManifest(name="rss", capability="feed", license="MIT",
                             requires_credentials=False, preference=10,
                             factory=lambda: RSSConnector(config))
