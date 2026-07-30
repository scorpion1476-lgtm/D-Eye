"""Acceptance tests for the 8 D-Eye skills.

Each skill is invoked either in-process against seeded data or through
its structured API. Skills that need live network (research,
web_discovery, repository_research) are tested via monkeypatched
router routes so no network is required.

Registration coverage: every skill in `deye.skills.REGISTRY` has:
- a `name` + `version` + `description` + `run` callable;
- a matching `plugin/d-eye/skills/<name>/SKILL.md` file with valid frontmatter.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from deye import skills as skills_pkg
from deye.core.config import Config
from deye.core.evidence import EvidenceStore
from deye.core.provenance import Envelope, ResearchPacket, Source, Trust


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "plugin" / "d-eye" / "skills"

EXPECTED_SKILLS = {
    "research", "evidence", "web_discovery", "browser_research",
    "repository_research", "source_quality", "offline_research",
    "connector_builder",
}


# ---------------------------------------------------------------------------
# 1. Registration + parity between Python impl and SKILL.md
# ---------------------------------------------------------------------------

def test_registry_contains_all_eight_skills():
    assert set(skills_pkg.REGISTRY) == EXPECTED_SKILLS
    for name, skill in skills_pkg.REGISTRY.items():
        assert skill.name == name
        assert skill.version
        assert skill.description
        assert callable(skill.run)


def test_list_skills_shape():
    listed = skills_pkg.list_skills()
    assert {s["name"] for s in listed} == EXPECTED_SKILLS
    for s in listed:
        for key in ("name", "version", "description", "requires_consent", "tags"):
            assert key in s


def test_invoke_rejects_unknown_skill():
    with pytest.raises(KeyError):
        skills_pkg.invoke("does-not-exist")


def test_every_registered_skill_has_a_matching_SKILL_md():
    for name in EXPECTED_SKILLS:
        path = SKILLS_DIR / name / "SKILL.md"
        assert path.exists(), f"missing SKILL.md at {path}"
        text = path.read_text()
        # Frontmatter present
        assert text.startswith("---")
        # name key matches the skill name
        assert f"name: {name}" in text
        # description key present
        assert "description:" in text
        # version key present
        assert "version:" in text


# ---------------------------------------------------------------------------
# 2. offline_research — real local FTS + extractive answer
# ---------------------------------------------------------------------------

def _seed_home(tmp_path: Path) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    os.environ["DEYE_HOME"] = str(home)
    cfg = Config.load()
    cfg.ensure_home()
    store = EvidenceStore(cfg.evidence_db)
    packet = ResearchPacket(query="seed")
    packet.envelopes.append(Envelope(
        content=("SQLite FTS5 supports the Porter tokenizer for keyword search "
                 "in a compact in-process index. Deep search combines BM25 "
                 "recall with a phrase boost."),
        source=Source(url="https://arxiv.org/seed",
                      connector="seed", title="seed-fts5"),
        trust=Trust(origin="local", untrusted=True),
    ))
    store.record_packet(packet)
    return cfg


def test_offline_research_fast_mode(tmp_path, monkeypatch):
    cfg = _seed_home(tmp_path)
    monkeypatch.setenv("DEYE_OFFLINE", "1")
    result = skills_pkg.invoke("offline_research", query="fts5",
                                mode="fast", config=cfg)
    assert result["mode"] == "fast"
    assert result["offline_env"] is True
    assert result["hits"], f"no hits: {result}"


def test_offline_research_deep_mode(tmp_path, monkeypatch):
    cfg = _seed_home(tmp_path)
    monkeypatch.setenv("DEYE_OFFLINE", "1")
    result = skills_pkg.invoke("offline_research", query="porter tokenizer",
                                mode="deep", config=cfg)
    assert result["hits"]


def test_offline_research_answer_mode(tmp_path, monkeypatch):
    cfg = _seed_home(tmp_path)
    monkeypatch.setenv("DEYE_OFFLINE", "1")
    result = skills_pkg.invoke("offline_research",
                                query="fts5 tokenizer", mode="answer",
                                config=cfg)
    assert "answer" in result
    assert result["answer"]["confidence"] >= 0.0
    assert result["corpus_size"] >= 1


def test_offline_research_unknown_mode_raises(tmp_path):
    cfg = _seed_home(tmp_path)
    with pytest.raises(ValueError):
        skills_pkg.invoke("offline_research", query="q", mode="bogus",
                          config=cfg)


# ---------------------------------------------------------------------------
# 3. evidence skill — query, export, delete, stats, changes
# ---------------------------------------------------------------------------

def test_evidence_skill_stats_and_query_scoped(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("DEYE_HOME", str(home))
    cfg = Config.load()
    cfg.ensure_home()
    store = EvidenceStore(cfg.evidence_db)
    for tenant in ("acme", "beta"):
        p = ResearchPacket(query="seed")
        p.envelopes.append(Envelope(
            content=f"content for {tenant}",
            source=Source(url=f"https://{tenant}/x",
                          connector="seed", title=f"{tenant}-title"),
        ))
        store.record_packet(p, tenant=tenant)
    stats = skills_pkg.invoke("evidence", action="stats", tenant="acme",
                               config=cfg)
    assert stats["stats"]["sources"] == 1
    q = skills_pkg.invoke("evidence", action="query", query="acme",
                           tenant="acme", config=cfg)
    assert q["count"] == 1


def test_evidence_skill_export_and_delete_scoped(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("DEYE_HOME", str(home))
    cfg = Config.load()
    cfg.ensure_home()
    store = EvidenceStore(cfg.evidence_db)
    p = ResearchPacket(query="seed")
    p.envelopes.append(Envelope(
        content="acme content",
        source=Source(url="https://acme/x", connector="seed", title="t"),
    ))
    store.record_packet(p, tenant="acme")

    export = skills_pkg.invoke("evidence", action="export",
                                tenant="acme", config=cfg)
    assert export["ok"] is True
    assert export["export"]["packet_count"] == 1

    # Fails closed without confirm_delete
    result = skills_pkg.invoke("evidence", action="delete", tenant="acme",
                                config=cfg)
    assert result["result"]["ok"] is False
    # Succeeds with confirm_delete=True
    result2 = skills_pkg.invoke("evidence", action="delete", tenant="acme",
                                 confirm_delete=True, config=cfg)
    assert result2["result"]["ok"] is True


# ---------------------------------------------------------------------------
# 4. source_quality skill
# ---------------------------------------------------------------------------

def test_source_quality_skill_scores_and_detects():
    rows = [
        {"url": "https://arxiv.org/paper",
         "title": "paper",
         "excerpt": "The new algorithm increased revenue by 12 percent.",
         "content_hash": "sha256:a"},
        {"url": "https://mirror.example/paper",
         "title": "paper",
         "excerpt": "The new algorithm did not increase revenue.",
         "content_hash": "sha256:b"},
    ]
    r = skills_pkg.invoke("source_quality", rows=rows, min_confidence=0.3)
    assert "quality" in r
    assert "contradictions" in r
    # At least the arxiv row should carry a positive score
    scores = r["quality"]["scores_by_url"]
    assert scores["https://arxiv.org/paper"]["score"] > 0


def test_source_quality_skill_empty_input():
    r = skills_pkg.invoke("source_quality", rows=[])
    assert r["quality"]["input_count"] == 0


# ---------------------------------------------------------------------------
# 5. browser_research skill (unavailable path is deterministic)
# ---------------------------------------------------------------------------

def test_browser_research_status_and_denied_click():
    status = skills_pkg.invoke("browser_research", action="status")
    assert "available" in status
    result = skills_pkg.invoke("browser_research", action="click",
                                url="https://example.org",
                                selector="button.submit")
    # Without a consent policy grant, click is refused before touching browser
    inner = result["result"]
    assert inner["ok"] is False
    assert ("consent" in inner["reason"].lower()
            or "playwright" in inner["reason"].lower())


# ---------------------------------------------------------------------------
# 6. web_discovery / research / repository_research — mock router route
# ---------------------------------------------------------------------------

def _mock_router_env(monkeypatch, patch_target: str):
    def _fake_route(cap, req):
        return Envelope(
            content=f"MOCK {cap} {req.get('query') or req.get('url') or req.get('repo')}",
            source=Source(url="https://mock/example", connector="mock",
                          title="mock"),
            trust=Trust(origin="local", untrusted=True),
        )

    class _FakeRouter:
        registry = None

        def route(self, cap, req):
            return _fake_route(cap, req)

        def health_all(self):
            return []

    def _fake_build_router(config=None, **kw):
        return _FakeRouter()

    monkeypatch.setattr(patch_target, _fake_build_router)


def test_web_discovery_skill_via_router(monkeypatch):
    _mock_router_env(monkeypatch, "deye.skills.web_discovery.build_router")
    r = skills_pkg.invoke("web_discovery", capability="search",
                           query="continuous pricing")
    assert r["ok"] is True
    assert r["capability"] == "search"
    assert "MOCK search continuous pricing" in r["content_preview"]
    assert r["trust"]["untrusted"] is True


def test_web_discovery_error_path_is_structured(monkeypatch):
    from deye.core.router import RouterError

    class _FailRouter:
        registry = None
        def route(self, cap, req):
            raise RouterError("no backend")
        def health_all(self):
            return []

    monkeypatch.setattr("deye.skills.web_discovery.build_router",
                        lambda config=None, **kw: _FailRouter())
    r = skills_pkg.invoke("web_discovery", capability="search", query="q")
    assert r["ok"] is False
    assert "no backend" in r["error"]


def test_repository_research_skill_via_router(monkeypatch):
    _mock_router_env(monkeypatch, "deye.skills.repository_research.build_router")
    r = skills_pkg.invoke("repository_research", repo="python/cpython")
    assert r["ok"] is True
    assert r["repo"] == "python/cpython"


def test_research_skill_end_to_end_over_mocked_router(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("DEYE_HOME", str(home))
    _mock_router_env(monkeypatch, "deye.skills.research.build_router")

    # research() also uses deye.app.research which uses deye.app.search/fetch;
    # those internally go through the router, and we replaced build_router.
    # Fast-fail against a real network by patching those too:
    import deye.app as _app

    def _fake_search(router, query):
        return _app.Envelope(  # type: ignore[attr-defined]
            content="MOCK search result", source=_app.Source(
                url="https://mock/1", connector="mock", title="mock"),
        )

    def _fake_fetch(router, url):
        return _app.Envelope(  # type: ignore[attr-defined]
            content="MOCK fetch page contents",
            source=_app.Source(url=url, connector="mock", title="mock"),
        )

    monkeypatch.setattr("deye.skills.research._research",
                        lambda router, query, **kw: ResearchPacket(
                            query=query,
                            envelopes=[Envelope(
                                content="MOCK fetch page contents about "
                                        "continuous pricing",
                                source=Source(url="https://mock/1",
                                              connector="mock", title="m"),
                            )],
                        ))
    r = skills_pkg.invoke("research",
                           query="continuous pricing", max_sources=1)
    assert r["source_count"] == 1
    assert "continuous pricing" in r["query"]
    assert r["answer"]["citations"]


# ---------------------------------------------------------------------------
# 7. connector_builder skill
# ---------------------------------------------------------------------------

def test_connector_builder_returns_valid_python_text():
    r = skills_pkg.invoke("connector_builder",
                           name="my_source",
                           capability="fetch",
                           description="Test connector.")
    text = r["module_text"]
    assert 'name = "my_source"' in text
    assert 'capability = "fetch"' in text
    assert "safe_get" in text
    assert "trust=Trust(origin=" in text
    # module compiles
    compile(text, "<generated>", "exec")


def test_connector_builder_writes_to_disk_when_out_path_given(tmp_path):
    out = tmp_path / "generated" / "my_source.py"
    r = skills_pkg.invoke("connector_builder", name="my_source",
                           capability="feed", out_path=str(out))
    assert r["written_to"] == str(out)
    assert out.exists()
    assert 'capability = "feed"' in out.read_text()


def test_connector_builder_rejects_bad_names():
    for bad in ("", "Bad Name", "1starts_with_digit", "x" * 100, "with-dash"):
        with pytest.raises(ValueError):
            skills_pkg.invoke("connector_builder", name=bad)


def test_connector_builder_rejects_bad_capability():
    with pytest.raises(ValueError):
        skills_pkg.invoke("connector_builder", name="ok",
                          capability="not-a-cap")
