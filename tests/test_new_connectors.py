"""Acceptance tests for the FOSS connectors added in Phase 4.

Every connector is exercised with a fake `safe_get` so tests never touch
the network. Assertions cover: manifest registration + preference,
health() shape, run() envelope shape (content + Source + Trust +
warnings + artifacts), and error paths.

Categories covered here:
    C03-F005 Reddit; C03-F006 YouTube; C03-F012 V2EX;
    social_stub covers the lawful-boundary rows in C03 by declaring
    them BLOCKED-BY-PLATFORM instead of scraping in violation of ToS.
"""
from __future__ import annotations

import json

import pytest

from deye.connectors import reddit, social_stub, v2ex, youtube


def _fake_get(payload: bytes | str, warnings=None):
    """Return a stand-in for `safe_get` yielding *payload*."""
    body = payload.encode("utf-8") if isinstance(payload, str) else payload

    def _f(url, *, limits, allowed_domains=None):
        return body, url, list(warnings or [])
    return _f


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------

def test_reddit_search_shape_and_manifest(monkeypatch):
    fake = {
        "data": {"children": [
            {"data": {
                "title": "sqlite-vec is out", "permalink": "/r/python/1/x/",
                "subreddit_name_prefixed": "r/python",
                "author": "alex", "score": 12, "num_comments": 3,
                "created_utc": 1700000000,
            }},
            {"data": {
                "title": "another post", "permalink": "/r/python/2/y/",
                "subreddit_name_prefixed": "r/python",
                "author": "sam", "score": 7, "num_comments": 1,
                "created_utc": 1700000100,
            }},
        ]}
    }
    monkeypatch.setattr(reddit, "safe_get", _fake_get(json.dumps(fake)))
    c = reddit.RedditSearch()
    env = c.run({"query": "sqlite-vec", "subreddit": "python", "limit": 5})
    assert env.source.connector == "reddit_search"
    assert env.trust.origin == "public_web"
    assert env.trust.untrusted is True
    assert "sqlite-vec is out" in env.content
    # artifact carries structured results
    art = next(a for a in env.artifacts if a["type"] == "reddit_search")
    assert len(art["results"]) == 2
    assert art["results"][0]["url"].endswith("/r/python/1/x/")

    ms = reddit.manifests()
    assert {m.name for m in ms} == {"reddit_search", "reddit_fetch"}
    for m in ms:
        assert m.license == "MIT"
        assert m.requires_credentials is False
        assert m.cost == "free"


def test_reddit_search_rejects_empty_query():
    with pytest.raises(Exception):
        reddit.RedditSearch().run({"query": ""})


def test_reddit_fetch_rejects_non_reddit_url():
    with pytest.raises(Exception):
        reddit.RedditFetch().run({"url": "https://example.com/x"})


def test_reddit_fetch_rewrites_to_json_endpoint(monkeypatch):
    captured = {}

    def _spy(url, *, limits, allowed_domains=None):
        captured["url"] = url
        return b"{\"ok\": true}", url, []
    monkeypatch.setattr(reddit, "safe_get", _spy)
    reddit.RedditFetch().run({"url": "https://www.reddit.com/r/python/comments/1abc/foo"})
    assert captured["url"].endswith(".json")


# ---------------------------------------------------------------------------
# V2EX
# ---------------------------------------------------------------------------

def test_v2ex_feed_hot_shape(monkeypatch):
    fake = [
        {"title": "topic 1", "url": "https://www.v2ex.com/t/1",
         "node": {"title": "python"}, "created": 1, "replies": 4},
        {"title": "topic 2", "url": "https://www.v2ex.com/t/2",
         "node": {"title": "programmer"}, "created": 2, "replies": 0},
    ]
    monkeypatch.setattr(v2ex, "safe_get", _fake_get(json.dumps(fake)))
    env = v2ex.V2exFeed().run({"mode": "hot"})
    assert "[python] topic 1" in env.content
    art = next(a for a in env.artifacts if a["type"] == "v2ex_topics")
    assert art["mode"] == "hot"
    assert len(art["results"]) == 2


def test_v2ex_feed_rejects_bad_mode():
    with pytest.raises(Exception):
        v2ex.V2exFeed().run({"mode": "trending"})


def test_v2ex_fetch_returns_topic_content(monkeypatch):
    payload = [{"id": 42, "title": "hello world", "url": "https://www.v2ex.com/t/42",
                "node": {"title": "share"}, "member": {"username": "alice"},
                "content": "some content"}]
    monkeypatch.setattr(v2ex, "safe_get", _fake_get(json.dumps(payload)))
    env = v2ex.V2exFetch().run({"topic_id": 42})
    assert "hello world" in env.content
    assert "some content" in env.content


def test_v2ex_fetch_rejects_missing_id():
    with pytest.raises(Exception):
        v2ex.V2exFetch().run({})


def test_v2ex_manifests_are_public_free():
    for m in v2ex.manifests():
        assert m.license == "MIT"
        assert m.requires_credentials is False
        assert m.cost == "free"
        assert m.origin == "public_web"


# ---------------------------------------------------------------------------
# YouTube (oEmbed + channel RSS)
# ---------------------------------------------------------------------------

def test_youtube_fetch_via_oembed(monkeypatch):
    fake = {
        "title": "How SQLite FTS5 works",
        "author_name": "Some Channel",
        "author_url": "https://www.youtube.com/some",
        "thumbnail_url": "https://i.ytimg.com/vi/x/hq.jpg",
    }
    monkeypatch.setattr(youtube, "safe_get", _fake_get(json.dumps(fake)))
    env = youtube.YouTubeFetch().run({"url": "https://youtu.be/xyz"})
    assert "How SQLite FTS5 works" in env.content
    assert env.source.title.startswith("YouTube:")
    art = next(a for a in env.artifacts if a["type"] == "youtube_oembed")
    assert art["data"]["author_name"] == "Some Channel"


def test_youtube_fetch_rejects_missing_url():
    with pytest.raises(Exception):
        youtube.YouTubeFetch().run({})


def test_youtube_channel_feed_shape(monkeypatch):
    rss_xml = '<?xml version="1.0"?><feed><entry><title>v1</title></entry></feed>'
    monkeypatch.setattr(youtube, "safe_get", _fake_get(rss_xml))
    env = youtube.YouTubeChannelFeed().run({"channel_id": "UCxxxxxxxxx"})
    assert "<feed>" in env.content
    art = next(a for a in env.artifacts if a["type"] == "youtube_channel_rss")
    assert art["channel_id"] == "UCxxxxxxxxx"


def test_youtube_channel_feed_rejects_missing_channel_id():
    with pytest.raises(Exception):
        youtube.YouTubeChannelFeed().run({})


# ---------------------------------------------------------------------------
# Social stubs (lawful boundary declarations)
# ---------------------------------------------------------------------------

def test_social_stubs_report_missing_and_carry_reason():
    ms = social_stub.manifests()
    names = {m.name for m in ms}
    assert names >= {"twitter_x", "linkedin", "facebook", "instagram",
                     "bilibili", "xiaohongshu"}
    for m in ms:
        instance = m.factory()
        h = instance.health()
        assert h.status == "missing", f"{m.name} should report missing"
        assert h.detail, f"{m.name} health.detail should carry the platform reason"
        # calling run() should raise with the same reason
        with pytest.raises(Exception) as exc:
            instance.run({"query": "anything"})
        assert h.detail[:20] in str(exc.value) or m.name in str(exc.value)


def test_social_stubs_are_last_resort_in_registry():
    # preference is very high so router prefers real connectors first
    for m in social_stub.manifests():
        assert m.preference >= 900


# ---------------------------------------------------------------------------
# Registry integration — the new connectors are wired into build_registry
# ---------------------------------------------------------------------------

def test_new_connectors_are_registered_in_router():
    from deye.app import build_registry

    reg = build_registry()
    names = {m.name for m in reg.manifests}
    assert names >= {
        "reddit_search", "reddit_fetch",
        "v2ex_feed", "v2ex_fetch",
        "youtube_fetch", "youtube_channel_feed",
        "twitter_x", "linkedin", "facebook",
        "instagram", "bilibili", "xiaohongshu",
    }
    # capabilities the new connectors extend
    capabilities = {m.capability for m in reg.manifests}
    assert {"search", "fetch", "feed"} <= capabilities
