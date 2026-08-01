"""Acceptance tests for the keyless YouTube transcript connector (C03-F006).

These exercise the real parse and envelope code against a realistic public
timedtext response (the same shape YouTube's keyless endpoint returns),
the clean no-captions degrade path, id extraction, and reachability through
the real router. A final live-network test drives the actual endpoint and
skips only when youtube.com is unreachable.
"""
from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from deye.connectors import youtube
from deye.connectors.base import ConnectorError
from deye.connectors.youtube import YouTubeTranscript, _video_id
from deye.core.config import Config

LIST_XML = (
    b'<?xml version="1.0" encoding="utf-8" ?>'
    b'<transcript_list><track id="0" name="" lang_code="en" '
    b'lang_original="English" lang_translated="English"/></transcript_list>'
)
TRANSCRIPT_XML = (
    b'<?xml version="1.0" encoding="utf-8" ?><transcript>'
    b'<text start="0" dur="2.5">Hello and welcome</text>'
    b'<text start="2.5" dur="3">to this &amp; that demo</text>'
    b'</transcript>'
)
EMPTY_LIST = b'<?xml version="1.0" ?><transcript_list></transcript_list>'


def _mock_safe_get(list_xml: bytes, transcript_xml: bytes):
    def _fake(url, *, limits, allowed_domains=None):
        if "type=list" in url:
            return list_xml, url, []
        return transcript_xml, url, []
    return _fake


def test_video_id_extraction_covers_common_url_forms():
    vid = "dQw4w9WgXcQ"
    assert _video_id(f"https://www.youtube.com/watch?v={vid}&t=1s") == vid
    assert _video_id(f"https://youtu.be/{vid}") == vid
    assert _video_id(f"https://www.youtube.com/shorts/{vid}") == vid
    assert _video_id(f"https://www.youtube.com/embed/{vid}") == vid
    assert _video_id(vid) == vid
    with pytest.raises(ConnectorError):
        _video_id("https://example.com/not-a-video")


def test_transcript_parses_public_captions(monkeypatch):
    monkeypatch.setattr(youtube, "safe_get", _mock_safe_get(LIST_XML, TRANSCRIPT_XML))
    env = YouTubeTranscript(Config()).run({"url": "https://youtu.be/dQw4w9WgXcQ"})
    # Real parse: both segments present, and &amp; is unescaped to &.
    assert "Hello and welcome" in env.content
    assert "to this & that demo" in env.content
    art = env.artifacts[0]
    assert art["type"] == "youtube_transcript"
    assert art["available"] is True
    assert art["video_id"] == "dQw4w9WgXcQ"
    assert art["lang"].startswith("en")
    assert art["segment_count"] == 2
    assert art["segments"][0]["start"] == 0.0
    # Inherited security posture: retrieved captions are untrusted evidence.
    assert env.trust.untrusted is True
    assert env.source.connector == "youtube_transcript"


def test_transcript_degrades_cleanly_when_no_public_captions(monkeypatch):
    monkeypatch.setattr(youtube, "safe_get", _mock_safe_get(EMPTY_LIST, b""))
    env = YouTubeTranscript(Config()).run({"url": "https://youtu.be/dQw4w9WgXcQ"})
    art = env.artifacts[0]
    assert art["available"] is False
    assert art["segments"] == []
    assert any("no public caption" in w for w in env.warnings)


def test_transcript_is_wired_into_the_real_router(monkeypatch):
    from deye.app import build_router, youtube_transcript
    monkeypatch.setattr(youtube, "safe_get", _mock_safe_get(LIST_XML, TRANSCRIPT_XML))
    router = build_router(Config())
    assert "transcript" in router.registry.capabilities()
    env = youtube_transcript(router, "https://youtu.be/dQw4w9WgXcQ")
    assert "Hello and welcome" in env.content


def test_transcript_cli_subcommand_is_registered():
    from deye.cli import build_parser
    args = build_parser().parse_args(["transcript", "https://youtu.be/dQw4w9WgXcQ"])
    assert args.command == "transcript"
    assert args.url == "https://youtu.be/dQw4w9WgXcQ"


def _yt_reachable() -> bool:
    try:
        urllib.request.urlopen("https://www.youtube.com/", timeout=5)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


@pytest.mark.skipif(not _yt_reachable(), reason="youtube.com unreachable from this host")
def test_transcript_live_endpoint_executes_end_to_end():
    """Drive the real keyless timedtext endpoint. A video may or may not have
    public captions, so we assert only that the live path runs and returns a
    well-formed envelope (available True or False), never a crash."""
    env = YouTubeTranscript(Config()).run(
        {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    art = env.artifacts[0]
    assert art["type"] == "youtube_transcript"
    assert art["video_id"] == "dQw4w9WgXcQ"
    assert isinstance(art["available"], bool)
    assert env.trust.untrusted is True
