"""C03-F010 Bilibili public video-info via the keyless `view` JSON endpoint.

Acceptance: a video reference (URL / BV id / av number) resolves to the keyless
`api.bilibili.com/x/web-interface/view` query; a successful response parses into
a structured, untrusted-evidence artifact; a non-zero business code degrades
cleanly; and the connector is reachable via the router capability `video.info`.
Bilibili *search* stays a documented boundary (WBI anti-bot signature).
"""
from __future__ import annotations

import json

import pytest

from deye.connectors import bilibili
from deye.connectors.base import ConnectorError

_VIEW_OK = {
    "code": 0, "message": "0",
    "data": {
        "bvid": "BV1xx411c7mD", "aid": 2,
        "title": "Example public video", "desc": "a public description",
        "duration": 125,
        "owner": {"name": "uploader-name", "mid": 999},
        "stat": {"view": 5417971, "like": 12000, "coin": 3000, "favorite": 8000},
    },
}
_VIEW_MISSING = {"code": -404, "message": "啥都木有", "data": None}


# -- reference extraction ---------------------------------------------------

def test_ref_to_query_accepts_url_bvid_av():
    assert bilibili._ref_to_query("https://www.bilibili.com/video/BV1xx411c7mD") == "bvid=BV1xx411c7mD"
    assert bilibili._ref_to_query("BV1xx411c7mD") == "bvid=BV1xx411c7mD"
    assert bilibili._ref_to_query("av2") == "aid=2"
    assert bilibili._ref_to_query("12345") == "aid=12345"


def test_ref_to_query_rejects_garbage():
    with pytest.raises(ConnectorError):
        bilibili._ref_to_query("not a video reference")


# -- run() with a stubbed fetch (no network) --------------------------------

def _stub_get(payload):
    def _get(url, *, limits, allowed_domains=None):
        return json.dumps(payload).encode("utf-8"), url, []
    return _get


def test_run_parses_view_json_into_artifact(monkeypatch):
    monkeypatch.setattr(bilibili, "safe_get", _stub_get(_VIEW_OK))
    env = bilibili.BilibiliVideoInfo().run({"url": "BV1xx411c7mD"})
    art = env.artifacts[0]
    assert art["type"] == "bilibili_video_info"
    assert art["available"] is True
    assert art["bvid"] == "BV1xx411c7mD"
    assert art["title"] == "Example public video"
    assert art["owner"] == "uploader-name"
    assert art["views"] == 5417971
    assert env.trust.untrusted is True                 # content is untrusted evidence
    assert "Example public video" in env.content


def test_run_degrades_cleanly_on_missing_video(monkeypatch):
    monkeypatch.setattr(bilibili, "safe_get", _stub_get(_VIEW_MISSING))
    env = bilibili.BilibiliVideoInfo().run({"url": "BV0000000000"})
    art = env.artifacts[0]
    assert art["available"] is False
    assert any("code" in w for w in env.warnings)


# -- router reachability + search boundary ----------------------------------

def test_video_info_capability_registered_and_routes(monkeypatch):
    monkeypatch.setattr(bilibili, "safe_get", _stub_get(_VIEW_OK))
    from deye.app import bilibili_info, build_router
    from deye.core.config import Config
    router = build_router(Config())
    assert "video.info" in router.registry.capabilities()
    env = bilibili_info(router, "BV1xx411c7mD")
    assert env.artifacts[0]["available"] is True


def test_bilibili_search_stays_a_documented_boundary():
    from deye.connectors.social_stub import PLATFORM_BOUNDARIES
    assert "bilibili" not in PLATFORM_BOUNDARIES          # generic stub removed
    assert "bilibili_search" in PLATFORM_BOUNDARIES        # search boundary kept
    reason = PLATFORM_BOUNDARIES["bilibili_search"].lower()
    assert "wbi" in reason or "signature" in reason


# -- live, skip-guarded -----------------------------------------------------

def test_live_bilibili_view_returns_real_info():
    """Hits the real keyless view API. Skips cleanly if the host is unreachable
    (offline clean clone) so it never blocks the core suite."""
    from deye.core.config import Config
    try:
        env = bilibili.BilibiliVideoInfo(Config()).run({"url": "BV1xx411c7mD"})
    except ConnectorError as exc:
        pytest.skip(f"bilibili unreachable in this environment: {exc}")
    art = env.artifacts[0]
    if not art.get("available"):
        pytest.skip(f"bilibili returned non-zero code live: {env.warnings}")
    assert art["bvid"] == "BV1xx411c7mD"
    assert art["title"]
    assert isinstance(art["views"], int)
