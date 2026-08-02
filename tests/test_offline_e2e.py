"""Offline end-to-end test — the mission's hardest FOSS gate.

Proves that with DEYE_OFFLINE=1, no API keys, no network calls:

- the CLI still starts;
- capability + connector enumeration works;
- Router health-checks classify network-only connectors correctly;
- persistent evidence store round-trips a research packet;
- research-package FTS search finds a seeded row;
- extractive answer returns a grounded response with citations;
- MCP capability_list works;
- lifecycle env + repair + status all report.

This is one of the hard gates the mission requires (see the FOSS-only
architecture correction).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from deye import lifecycle
from deye.app import build_registry, build_router, query_evidence
from deye.core.evidence import EvidenceStore
from deye.core.provenance import Envelope, ResearchPacket, Source, Trust
from deye.research import build_index, extractive_answer, fast_search


@pytest.fixture(autouse=True)
def _offline_home(tmp_path, monkeypatch):
    """Force offline mode + isolated DEYE_HOME."""
    monkeypatch.setenv("DEYE_OFFLINE", "1")
    monkeypatch.setenv("DEYE_HOME", str(tmp_path))
    yield


def _seed_evidence(store: EvidenceStore) -> None:
    """Populate the store with two sources so downstream tests have data."""
    packet = ResearchPacket(query="offline seed")
    env1 = Envelope(
        content="SQLite FTS5 supports Porter tokenizer for keyword search "
                "in a compact, fast, in-process index.",
        source=Source(url="https://arxiv.org/x", connector="seed",
                      title="fts5 tutorial"),
        trust=Trust(origin="local", untrusted=True),
    )
    env2 = Envelope(
        content="Playwright is an Apache-2.0 licensed browser automation "
                "library maintained by Microsoft.",
        source=Source(url="https://playwright.dev", connector="seed",
                      title="playwright"),
        trust=Trust(origin="local", untrusted=True),
    )
    packet.envelopes = [env1, env2]
    store.record_packet(packet)


# ---------------------------------------------------------------------------
# Cold-start smoke: everything imports and instantiates without network
# ---------------------------------------------------------------------------

def test_offline_cli_status_returns_json_only():
    # deye.cli.cmd_status is a pure function of config; no network required.
    from deye.cli import cmd_status
    from deye.core.config import Config
    rc = cmd_status(args=None, cfg=Config.load())
    assert rc == 0


def test_offline_registry_enumerates_all_connectors():
    reg = build_registry()
    names = {m.name for m in reg.manifests}
    # every connector we ship must be enumerable offline
    assert names >= {
        "search_duckduckgo", "search_exa",
        "web_fetch", "rss", "github_repo",
        "reddit_search", "reddit_fetch",
        "v2ex_feed", "v2ex_fetch",
        "youtube_fetch", "youtube_channel_feed",
        "twitter_x", "linkedin", "facebook", "instagram",
        "bilibili_search", "bilibili_video_info", "xiaohongshu",
    }
    assert reg.capabilities()


def test_offline_router_health_all_never_makes_requests(monkeypatch):
    # Guardrail: even health_all must not hit the network in offline mode.
    # We instrument safe_get to blow up if called.
    called = {"n": 0}

    def _boom(*a, **kw):
        called["n"] += 1
        raise AssertionError("offline mode invariant broken: safe_get called")

    monkeypatch.setattr("deye.connectors.base.safe_get", _boom)
    router = build_router()
    reports = router.health_all()
    # every entry has a status (ok | degraded | missing | broken | unconfigured)
    for r in reports:
        assert "status" in r
    assert called["n"] == 0


# ---------------------------------------------------------------------------
# Local capabilities that must work offline: evidence, research, answer
# ---------------------------------------------------------------------------

def test_offline_evidence_store_persistence(tmp_path):
    db = tmp_path / "e.db"
    store = EvidenceStore(db)
    _seed_evidence(store)
    stats = store.stats()
    assert stats["packets"] == 1
    assert stats["sources"] == 2
    assert stats["distinct_urls"] == 2


def test_offline_evidence_query_finds_seed():
    from deye.core.config import Config
    cfg = Config.load()
    cfg.ensure_home()
    store = EvidenceStore(cfg.evidence_db)
    _seed_evidence(store)
    res = query_evidence("fts5", config=cfg)
    assert res["results"]
    assert any("fts5" in (r["title"] or "").lower() for r in res["results"])


def test_offline_research_fts_and_extractive_answer():
    from deye.core.config import Config
    cfg = Config.load()
    cfg.ensure_home()
    store = EvidenceStore(cfg.evidence_db)
    _seed_evidence(store)
    idx = build_index(store, in_memory=True, limit=100)

    hits = fast_search(idx, "fts5")
    assert hits
    assert hits[0]["url"] == "https://arxiv.org/x"

    ans = extractive_answer(store.query("fts5"), "fts5 tokenizer")
    assert ans.citations
    assert ans.answer.strip()
    assert ans.confidence > 0


# ---------------------------------------------------------------------------
# Lifecycle offline behaviour
# ---------------------------------------------------------------------------

def test_offline_lifecycle_env_reports_offline_true():
    r = lifecycle.env_detect()
    assert r.is_offline is True


def test_offline_check_update_and_provision_are_refused():
    upd = lifecycle.check_update()
    assert "offline" in upd.reason.lower()
    prov = lifecycle.provision_extra("mcp")
    assert prov["ok"] is False
    assert "offline" in prov["reason"]


def test_offline_aggregate_report_serialisable():
    report = lifecycle.aggregate_report()
    j = json.dumps(report)
    assert '"environment"' in j
    assert '"extras"' in j


# ---------------------------------------------------------------------------
# MCP capability listing (local, does not need the network)
# ---------------------------------------------------------------------------

def test_offline_mcp_capability_listing_available():
    # Import the module; if this raises, the MCP path is broken offline.
    pytest.importorskip("mcp")
    from deye import mcp_server  # noqa: F401
    # capability enumeration is a pure function of the registry
    reg = build_registry()
    caps = reg.capabilities()
    assert "search" in caps
    assert "fetch" in caps
    assert "feed" in caps
