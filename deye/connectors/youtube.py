"""YouTube read-only connector - oEmbed metadata, channel RSS, and public
captions, no key required.

Three lawful, keyless surfaces are exposed:

    ``fetch``       request: {"url": "https://youtu.be/<id>"}
                              → oEmbed metadata (title, author, thumbnail).

    ``feed``        request: {"channel_id": "UCxxxxxxxxx"}
                              → the channel's public RSS videos feed.

    ``transcript``  request: {"url": "https://youtu.be/<id>"}
                              → the video's public captions, if the uploader
                                published any, via YouTube's public timedtext
                                endpoint. Keyless, no login, no scraping of the
                                watch page. Degrades cleanly (available=False)
                                when a video has no public caption track.

Free-text video search is not done here: it needs the YouTube Data API v3
key path, which is kept off the keyless core. Callers who want to find
videos use the keyless ``search`` capability with a ``site:youtube.com``
filter, then pass the resulting URL to ``fetch`` or ``transcript``.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse

from deye.connectors.base import ConnectorError, safe_get, timed_health
from deye.connectors.rss import _safe_fromstring  # XXE/DOCTYPE-guarded XML parse
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport

# Accepts watch URLs, youtu.be, /embed/, /shorts/, or a bare 11-char id.
_VIDEO_ID_RE = re.compile(
    r"(?:v=|/embed/|/shorts/|youtu\.be/|/v/)([A-Za-z0-9_-]{11})"
)


def _video_id(url: str) -> str:
    """Extract the 11-character YouTube video id from any common URL form."""
    s = (url or "").strip()
    m = _VIDEO_ID_RE.search(s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    raise ConnectorError(f"could not extract a YouTube video id from {url!r}")


def _parse_track_list(body: bytes) -> list[dict]:
    """Parse the timedtext ``type=list`` XML into caption-track descriptors."""
    try:
        root = _safe_fromstring(body)
    except Exception:  # noqa: BLE001 - no/invalid list means no public captions
        return []
    tracks = []
    for node in root.iter("track"):
        a = node.attrib
        code = a.get("lang_code") or a.get("lang") or ""
        if not code:
            continue
        tracks.append({
            "lang_code": code,
            "name": a.get("name", ""),
            "kind": a.get("kind", ""),  # "asr" = auto-generated
            "lang_original": a.get("lang_original", ""),
        })
    return tracks


def _pick_track(tracks: list[dict]) -> dict:
    """Prefer a human English track, then any English, then the first track."""
    for t in tracks:
        if t["lang_code"].startswith("en") and t["kind"] != "asr":
            return t
    for t in tracks:
        if t["lang_code"].startswith("en"):
            return t
    return tracks[0]


def _extract_caption_tracks(html_bytes: bytes) -> list[dict]:
    """Extract the public caption-track list from a watch page's player
    response. This reads only the public ``captionTracks`` metadata (baseUrl,
    languageCode, kind) that YouTube itself embeds in the public page. No
    login, no cookies, no anti-bot circumvention."""
    text = html_bytes.decode("utf-8", errors="replace")
    key = '"captionTracks":'
    i = text.find(key)
    if i == -1:
        return []
    j = text.find("[", i)
    if j == -1:
        return []
    depth = 0
    end = -1
    for k in range(j, min(len(text), j + 500_000)):
        c = text[k]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = k
                break
    if end == -1:
        return []
    try:
        raw = json.loads(text[j:end + 1])
    except json.JSONDecodeError:
        return []
    tracks = []
    for t in raw:
        base = t.get("baseUrl")
        if not base:
            continue
        tracks.append({
            "lang_code": t.get("languageCode", ""),
            "kind": t.get("kind", ""),        # "asr" = auto-generated
            "name": "",
            "base_url": base,
        })
    return tracks


def _parse_transcript(body: bytes) -> list[dict]:
    """Parse the timedtext transcript XML into timed, unescaped text segments."""
    try:
        root = _safe_fromstring(body)
    except Exception:  # noqa: BLE001 - empty/invalid transcript
        return []
    segments = []
    for node in root.iter("text"):
        raw = node.text or ""
        text = html.unescape(raw).replace("\n", " ").strip()
        if not text:
            continue
        try:
            start = float(node.attrib.get("start", "0") or 0)
        except ValueError:
            start = 0.0
        try:
            dur = float(node.attrib.get("dur", "0") or 0)
        except ValueError:
            dur = 0.0
        segments.append({"start": start, "dur": dur, "text": text})
    return segments


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


class YouTubeTranscript:
    """Public captions for a video, via YouTube's keyless timedtext endpoint.

    No login, no watch-page scraping, no anti-bot circumvention: it lists the
    public caption tracks the uploader published and returns the chosen track's
    timed text. If a video has no public captions it returns an envelope with
    ``available=False`` and a warning rather than raising.
    """

    name = "youtube_transcript"
    capability = "transcript"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "public timedtext"))

    def run(self, request: dict) -> Envelope:
        url = (request.get("url") or "").strip()
        vid = _video_id(url)
        lang_pref = (request.get("lang") or "").strip()
        warnings: list[str] = []

        def _choose(tracks: list[dict]) -> dict:
            if lang_pref:
                t = next((t for t in tracks if t["lang_code"].startswith(lang_pref)), None)
                if t:
                    return t
            return _pick_track(tracks)

        def _success(segments: list[dict], track: dict) -> Envelope:
            text = " ".join(s["text"] for s in segments)
            env = Envelope(
                content=text[:20000],
                source=Source(url=url, connector=self.name,
                              title=f"YouTube transcript: {vid} [{track['lang_code']}]"),
                trust=Trust(origin="public_web", untrusted=True),
                warnings=list(warnings),
            )
            env.artifacts.append({
                "type": "youtube_transcript", "video_id": vid,
                "lang": track["lang_code"], "auto_generated": track.get("kind") == "asr",
                "available": True, "segment_count": len(segments),
                "segments": segments[:2000],
            })
            return env

        # Path 1: the legacy public timedtext list endpoint.
        try:
            list_url = ("https://www.youtube.com/api/timedtext?type=list&v="
                        + urllib.parse.quote(vid))
            list_body, _f, w = safe_get(list_url, limits=self.config.limits)
            warnings += w
            tracks = _parse_track_list(list_body)
            if tracks:
                track = _choose(tracks)
                tt = ("https://www.youtube.com/api/timedtext?v="
                      + urllib.parse.quote(vid) + "&lang="
                      + urllib.parse.quote(track["lang_code"]))
                if track.get("kind"):
                    tt += "&kind=" + urllib.parse.quote(track["kind"])
                if track.get("name"):
                    tt += "&name=" + urllib.parse.quote(track["name"])
                body, _f2, w2 = safe_get(tt, limits=self.config.limits)
                warnings += w2
                segments = _parse_transcript(body)
                if segments:
                    return _success(segments, track)
        except Exception as exc:  # noqa: BLE001 - fall through to the page path
            warnings.append(f"timedtext list path failed: {exc}")

        # Path 2: the public watch-page player response (captionTracks baseUrl).
        try:
            watch = "https://www.youtube.com/watch?v=" + urllib.parse.quote(vid)
            page, _f3, w3 = safe_get(watch, limits=self.config.limits)
            warnings += w3
            tracks = _extract_caption_tracks(page)
            if tracks:
                track = _choose(tracks)
                body, _f4, w4 = safe_get(track["base_url"], limits=self.config.limits)
                warnings += w4
                segments = _parse_transcript(body)
                if segments:
                    return _success(segments, track)
        except Exception as exc:  # noqa: BLE001 - degrade cleanly
            warnings.append(f"watch-page path failed: {exc}")

        env = Envelope(
            content="(no public captions available for this video)",
            source=Source(url=url, connector=self.name,
                          title=f"YouTube transcript: {vid}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings + ["no public caption tracks for this video"],
        )
        env.artifacts.append({"type": "youtube_transcript", "video_id": vid,
                              "available": False, "segments": []})
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
        ConnectorManifest(name="youtube_transcript", capability="transcript", license="MIT",
                          requires_credentials=False, cost="free", preference=40,
                          origin="public_web",
                          factory=lambda: YouTubeTranscript(config)),
    ]
