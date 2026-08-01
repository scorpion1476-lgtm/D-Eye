"""Acceptance tests for the second batch of FOSS connectors + browser
profiles + backend event bus + multi-source orchestrator.

Every test uses monkeypatched `safe_get` so no network is hit.
Covers: C03-F013 Xueqiu, C03-F014 Xiaoyuzhou, C03-F015 multi-source
research, C04-F002 browser profiles, C10-F005 event-driven workflows.
"""
from __future__ import annotations

import pytest

from deye.backend import Queue
from deye.backend.events import EventBus
from deye.browser import profiles as bp
from deye.connectors import xiaoyuzhou, xueqiu


def _fake_get(payload):
    body = payload.encode("utf-8") if isinstance(payload, str) else payload

    def _f(url, *, limits, allowed_domains=None):
        return body, url, []
    return _f


# ---------------------------------------------------------------------------
# Xueqiu
# ---------------------------------------------------------------------------

def test_xueqiu_fetch_returns_envelope(monkeypatch):
    monkeypatch.setattr(xueqiu, "safe_get",
                        _fake_get("<html><body>SH600519 kweichow moutai</body></html>"))
    c = xueqiu.XueqiuFetch()
    env = c.run({"symbol": "sh600519"})
    assert env.source.connector == "xueqiu_fetch"
    assert env.trust.untrusted is True
    assert "SH600519" in env.content
    art = next(a for a in env.artifacts if a["type"] == "xueqiu_symbol")
    assert art["symbol"] == "SH600519"


def test_xueqiu_rejects_bad_symbol():
    with pytest.raises(Exception):
        xueqiu.XueqiuFetch().run({"symbol": ""})
    with pytest.raises(Exception):
        xueqiu.XueqiuFetch().run({"symbol": "x" * 100})


def test_xueqiu_manifest_shape():
    ms = xueqiu.manifests()
    assert len(ms) == 1
    assert ms[0].name == "xueqiu_fetch"
    assert ms[0].requires_credentials is False
    assert ms[0].cost == "free"
    assert ms[0].license == "MIT"


# ---------------------------------------------------------------------------
# Xiaoyuzhou
# ---------------------------------------------------------------------------

def test_xiaoyuzhou_fetch_returns_envelope(monkeypatch):
    monkeypatch.setattr(xiaoyuzhou, "safe_get",
                        _fake_get("<html><title>ep-title</title></html>"))
    env = xiaoyuzhou.XiaoyuzhouFetch().run({"episode_id": "abc123"})
    assert env.source.connector == "xiaoyuzhou_fetch"
    assert "ep-title" in env.content
    art = next(a for a in env.artifacts if a["type"] == "xiaoyuzhou_episode")
    assert art["episode_id"] == "abc123"


def test_xiaoyuzhou_rejects_bad_id():
    with pytest.raises(Exception):
        xiaoyuzhou.XiaoyuzhouFetch().run({})
    with pytest.raises(Exception):
        xiaoyuzhou.XiaoyuzhouFetch().run({"episode_id": "!!!"})


# ---------------------------------------------------------------------------
# Registry integration for the new pair
# ---------------------------------------------------------------------------

def test_new_connectors_are_in_registry():
    from deye.app import build_registry
    reg = build_registry()
    names = {m.name for m in reg.manifests}
    assert "xueqiu_fetch" in names
    assert "xiaoyuzhou_fetch" in names


# ---------------------------------------------------------------------------
# Multi-source research orchestrator
# ---------------------------------------------------------------------------

def test_multi_source_search_aggregates_and_dedups(monkeypatch):
    """Simulate two search backends both returning the same URL/content
    hash; the orchestrator should dedup them into one cluster."""
    from deye.core.provenance import Envelope, Source, Trust
    from deye.research.multi_source import multi_source_search

    class _FakeReg:
        def for_capability(self, cap):
            # Simulate two 'search' manifests + zero 'feed' manifests.
            class Manifest:
                def __init__(self, name):
                    self.name = name
                    self.capability = "search"
                    self.factory = True
            if cap == "search":
                return [Manifest("a"), Manifest("b")]
            return []

    class _FakeRouter:
        registry = _FakeReg()

        def route_named(self, name, request):
            return Envelope(
                content="same content",
                source=Source(url="https://x/y", connector="fake",
                              title="same"),
                trust=Trust(origin="public_web"),
            )

    result = multi_source_search(_FakeRouter(), "q", max_workers=1)
    assert result.packet.envelopes  # got envelopes
    # exact URL twice → one cluster reason=exact_url
    assert any(c["reason"] == "exact_url" for c in result.dedup_clusters)


def test_multi_source_captures_per_source_errors():
    from deye.research.multi_source import multi_source_search

    class _FakeReg:
        def for_capability(self, cap):
            class M:
                def __init__(self, name):
                    self.name = name
                    self.factory = True
            return [M("bad")]

    class _FakeRouter:
        registry = _FakeReg()

        def route_named(self, name, request):
            raise RuntimeError("boom")

    result = multi_source_search(_FakeRouter(), "q", capabilities=("search",),
                                 max_workers=1)
    assert "bad" in result.per_source_errors
    assert "boom" in result.per_source_errors["bad"]


# ---------------------------------------------------------------------------
# Browser profiles
# ---------------------------------------------------------------------------

def test_browser_profile_lifecycle(monkeypatch, tmp_path):
    monkeypatch.setenv(bp.PROFILE_ROOT_ENV if hasattr(bp, "PROFILE_ROOT_ENV")
                       else "DEYE_BROWSER_PROFILES", str(tmp_path))
    # Create
    p = bp.create_profile("work")
    assert p.exists()
    assert p.name == "work"
    # List
    profs = bp.list_profiles()
    assert any(x.name == "work" for x in profs)
    # Delete refused without confirm
    result = bp.remove_profile("work")
    assert result["ok"] is False
    # Delete confirmed
    result = bp.remove_profile("work", confirm=True)
    assert result["ok"] is True
    assert not p.exists()


def test_browser_profile_rejects_bad_names(monkeypatch, tmp_path):
    monkeypatch.setenv("DEYE_BROWSER_PROFILES", str(tmp_path))
    for bad in ("", "with spaces", "../evil", "toolong-" + "x" * 100):
        with pytest.raises(ValueError):
            bp.create_profile(bad)


def test_browser_profile_report_structure(monkeypatch, tmp_path):
    monkeypatch.setenv("DEYE_BROWSER_PROFILES", str(tmp_path))
    bp.create_profile("one")
    bp.create_profile("two")
    r = bp.profile_report()
    assert r["count"] == 2
    assert "cookies live only" in r["boundary"]


# ---------------------------------------------------------------------------
# Event-driven workflows (Queue-backed)
# ---------------------------------------------------------------------------

def test_event_bus_dispatch_calls_subscribers_and_records_job(tmp_path):
    q = Queue(tmp_path / "q.db")
    bus = EventBus(queue=q)
    received: list[dict] = []
    bus.subscribe("evidence.saved", lambda payload: received.append(payload))
    result = bus.dispatch("evidence.saved", {"url": "https://x"},
                          tenant="acme")
    assert result["subscriber_count"] == 1
    assert received == [{"url": "https://x"}]
    stats = q.stats(tenant="acme")
    assert stats.get("done") == 1


def test_event_bus_captures_handler_errors(tmp_path):
    q = Queue(tmp_path / "q.db")
    bus = EventBus(queue=q)

    def bad(_):
        raise RuntimeError("boom")

    bus.subscribe("x", bad)
    result = bus.dispatch("x", {}, tenant="t")
    assert "boom" in " ".join(result["errors"])
    stats = q.stats(tenant="t")
    assert stats.get("failed") == 1


def test_event_bus_subscribe_and_unsubscribe(tmp_path):
    q = Queue(tmp_path / "q.db")
    bus = EventBus(queue=q)
    handler = lambda _: 1  # noqa: E731
    bus.subscribe("t", handler)
    bus.subscribe("t", handler)  # idempotent
    assert len(bus.subscribers["t"]) == 1
    bus.unsubscribe("t", handler)
    assert bus.subscribers["t"] == []
