"""Bilibili public video-info connector - keyless, read-only.

Bilibili publishes a documented, keyless JSON endpoint for a single video's
public metadata:

    https://api.bilibili.com/x/web-interface/view?bvid=<BVID>
    https://api.bilibili.com/x/web-interface/view?aid=<AID>

It returns the same public facts the video page shows (title, uploader,
description, duration, publish time, view/like/coin counts) with no login, no
cookie, and no anti-bot signature. This connector reads only that public
endpoint through D-Eye's SSRF-safe fetch path and labels the result untrusted
evidence. It degrades cleanly (available=False) when a video does not exist or
the endpoint returns a non-zero business code.

Free-text Bilibili *search* is deliberately NOT implemented here: the public
search endpoint now requires a WBI (``w_rid``) request signature that exists to
deter automated clients. Producing that signature to access search would be
circumventing an anti-bot control, which the build rules forbid, so the search
capability stays a documented boundary (see connectors/social_stub.py).
"""
from __future__ import annotations

import json
import re

from deye.connectors.base import ConnectorError, safe_get, timed_health
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport

_BVID_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_AID_RE = re.compile(r"(?:av|aid=)(\d+)", re.IGNORECASE)

_API = "https://api.bilibili.com/x/web-interface/view"


def _ref_to_query(ref: str) -> str:
    """Turn any common Bilibili reference into the API query string.

    Accepts a full video URL, a b23.tv short link path, a bare BV id, or an
    av/aid number. Prefers the BV id when both appear.
    """
    s = (ref or "").strip()
    if not s:
        raise ConnectorError("bilibili needs a video url, BV id, or av number")
    m = _BVID_RE.search(s)
    if m:
        return "bvid=" + m.group(1)
    m = _AID_RE.search(s)
    if m:
        return "aid=" + m.group(1)
    if s.isdigit():
        return "aid=" + s
    raise ConnectorError(f"could not extract a Bilibili BV id or av number from {ref!r}")


class BilibiliVideoInfo:
    name = "bilibili_video_info"
    capability = "video.info"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "public view API"))

    def run(self, request: dict) -> Envelope:
        ref = (request.get("url") or request.get("ref")
               or request.get("bvid") or request.get("id") or "").strip()
        query = _ref_to_query(ref)
        url = f"{_API}?{query}"
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise ConnectorError(f"bilibili returned non-JSON: {exc}") from exc

        code = data.get("code")
        if code != 0:
            env = Envelope(
                content=f"(bilibili video unavailable: {data.get('message') or code})",
                source=Source(url=ref, connector=self.name,
                              title=f"Bilibili: {ref}"),
                trust=Trust(origin="public_web", untrusted=True),
                warnings=warnings + [f"bilibili business code {code}: {data.get('message')}"],
            )
            env.artifacts.append({"type": "bilibili_video_info", "available": False,
                                  "code": code, "ref": ref})
            return env

        d = data.get("data") or {}
        owner = d.get("owner") or {}
        stat = d.get("stat") or {}
        info = {
            "bvid": d.get("bvid", ""),
            "aid": d.get("aid"),
            "title": d.get("title", ""),
            "desc": d.get("desc", ""),
            "owner": owner.get("name", ""),
            "owner_mid": owner.get("mid"),
            "duration_s": d.get("duration"),
            "pubdate": d.get("pubdate"),
            "views": stat.get("view"),
            "likes": stat.get("like"),
            "coins": stat.get("coin"),
            "favorites": stat.get("favorite"),
            "url": f"https://www.bilibili.com/video/{d.get('bvid', '')}",
        }
        content = "\n".join([
            f"Title: {info['title']}",
            f"Uploader: {info['owner']}",
            f"Duration (s): {info['duration_s']}",
            f"Views: {info['views']}  Likes: {info['likes']}",
            f"URL: {info['url']}",
            "",
            (info["desc"] or "").strip(),
        ])
        env = Envelope(
            content=content[:20000],
            source=Source(url=info["url"] or ref, connector=self.name,
                          title=f"Bilibili: {info['title'] or info['bvid']}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "bilibili_video_info", "available": True, **info})
        return env


def manifests(config: Config | None = None) -> list[ConnectorManifest]:
    return [
        ConnectorManifest(
            name="bilibili_video_info", capability="video.info", license="MIT",
            requires_credentials=False, cost="free", preference=40,
            origin="public_web",
            factory=lambda: BilibiliVideoInfo(config),
        ),
    ]
