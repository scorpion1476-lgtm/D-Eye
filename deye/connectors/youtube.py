"""YouTube read-only connector — oEmbed metadata + channel RSS, no key required.

Two lawful, keyless surfaces are exposed:

    ``fetch``   request: {"url": "https://youtu.be/<id>"}
                          → oEmbed metadata (title, author, thumbnail).

    ``feed``    request: {"channel_id": "UCxxxxxxxxx"}
                          → the channel's public RSS videos feed.

Deliberately NOT implemented (keyless search would violate ToS on the
scraped HTML surface and needs YouTube Data API v3 for the lawful path;
kept as an optional adapter behind an opt-in extra):

    - free-text video search
    - transcripts / captions (subject to per-video restrictions)
    - user account / write actions

Downstream callers that need search must either provide a YouTube Data
API key (kept as a disabled-by-default adapter) or use the
``search`` capability against the DuckDuckGo connector and filter by
``site:youtube.com``.
"""
from __future__ import annotations

import json
import urllib.parse

from deye.connectors.base import ConnectorError, safe_get, timed_health
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport


class YouTubeFetch:
    name = "youtube_fetch"
    capability = "fetch"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "public oEmbed"))

    def run(self, request: dict) -> Envelope:
        url = (request.get("url") or "").strip()
        if not url:
            raise ConnectorError("youtube_fetch needs 'url'")
        oembed = ("https://www.youtube.com/oembed?url=" + urllib.parse.quote(url)
                  + "&format=json")
        body, final_url, warnings = safe_get(oembed, limits=self.config.limits)
        text = body.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConnectorError(f"youtube oEmbed returned non-JSON: {exc}") from exc
        content = "\n".join([
            f"Title: {data.get('title', '')}",
            f"Author: {data.get('author_name', '')}",
            f"Author URL: {data.get('author_url', '')}",
            f"Thumbnail: {data.get('thumbnail_url', '')}",
            f"Original URL: {url}",
        ])
        env = Envelope(
            content=content,
            source=Source(url=url, connector=self.name,
                          title=f"YouTube: {data.get('title') or url}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "youtube_oembed", "data": data})
        return env


class YouTubeChannelFeed:
    name = "youtube_channel_feed"
    capability = "feed"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "public channel RSS"))

    def run(self, request: dict) -> Envelope:
        channel = (request.get("channel_id") or "").strip()
        if not channel:
            raise ConnectorError("youtube_channel_feed needs 'channel_id' (UCxxx)")
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={urllib.parse.quote(channel)}"
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        text = body.decode("utf-8", errors="replace")
        # Parse minimally without pulling in defusedxml here (we hand it off
        # unchanged to callers who want richer parsing). Truncate to keep
        # envelope size manageable.
        env = Envelope(
            content=text[:20000],
            source=Source(url=final_url, connector=self.name,
                          title=f"YouTube channel: {channel}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "youtube_channel_rss", "channel_id": channel})
        return env


def manifests(config: Config | None = None) -> list[ConnectorManifest]:
    return [
        ConnectorManifest(name="youtube_fetch", capability="fetch", license="MIT",
                          requires_credentials=False, cost="free", preference=40,
                          origin="public_web",
                          factory=lambda: YouTubeFetch(config)),
        ConnectorManifest(name="youtube_channel_feed", capability="feed", license="MIT",
                          requires_credentials=False, cost="free", preference=40,
                          origin="public_web",
                          factory=lambda: YouTubeChannelFeed(config)),
    ]
