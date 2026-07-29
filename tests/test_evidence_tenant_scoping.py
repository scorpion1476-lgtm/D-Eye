"""Multi-tenant EvidenceStore acceptance tests.

Verifies the per-tenant scoping the store gained this session:
- record_packet + query + stats + changed_since + delete_tenant + export_tenant
  all honour a tenant argument;
- owner-scope (tenant=None) still sees every row;
- default tenant cannot be deleted via delete_tenant (fail-closed);
- confirm=True required for destructive delete;
- schema migration works on legacy databases (adds `tenant` column with
  default 'default' — no data loss).

Promotes C06-F014 (evidence deletion + export) and C12-F032 (multi-user
isolation) from IMPL-NOT-VERIFIED to PRODUCTION READY. C10-F010 (deletion
+ data export) same.
"""
from __future__ import annotations

import sqlite3

import pytest

from deye.core.evidence import EvidenceStore
from deye.core.provenance import Envelope, ResearchPacket, Source, Trust


def _make_packet(query: str, urls: list[str]) -> ResearchPacket:
    packet = ResearchPacket(query=query)
    for url in urls:
        packet.envelopes.append(Envelope(
            content=f"content for {url}",
            source=Source(url=url, connector="seed",
                          title=f"title:{url}"),
            trust=Trust(origin="local", untrusted=True),
        ))
    return packet


# ---------------------------------------------------------------------------
# record_packet honours tenant
# ---------------------------------------------------------------------------

def test_record_packet_tags_rows_with_tenant(tmp_path):
    store = EvidenceStore(tmp_path / "e.db")
    store.record_packet(_make_packet("a", ["https://a/1"]), tenant="acme")
    store.record_packet(_make_packet("b", ["https://b/2"]), tenant="beta")
    # owner scope sees both
    all_rows = store.query("", tenant=None, limit=10)
    assert {r["tenant"] for r in all_rows} == {"acme", "beta"}
    # tenant scope sees only own
    acme_rows = store.query("", tenant="acme", limit=10)
    assert {r["tenant"] for r in acme_rows} == {"acme"}
    beta_rows = store.query("", tenant="beta", limit=10)
    assert {r["tenant"] for r in beta_rows} == {"beta"}


def test_query_scoped_by_tenant_and_text(tmp_path):
    store = EvidenceStore(tmp_path / "e.db")
    store.record_packet(_make_packet("q", ["https://a/x"]), tenant="acme")
    store.record_packet(_make_packet("q", ["https://b/x"]), tenant="beta")
    # text filter across tenants
    rows = store.query("https://a", tenant=None)
    assert len(rows) == 1
    # text filter with tenant scope
    assert store.query("https://a", tenant="beta") == []
    assert len(store.query("https://a", tenant="acme")) == 1


def test_stats_scoped_by_tenant(tmp_path):
    store = EvidenceStore(tmp_path / "e.db")
    store.record_packet(_make_packet("a", ["https://a/1", "https://a/2"]),
                        tenant="acme")
    store.record_packet(_make_packet("b", ["https://b/1"]), tenant="beta")
    total = store.stats()
    assert total["sources"] == 3
    acme = store.stats(tenant="acme")
    assert acme["sources"] == 2 and acme["packets"] == 1
    beta = store.stats(tenant="beta")
    assert beta["sources"] == 1 and beta["packets"] == 1


def test_changed_since_scoped_by_tenant(tmp_path):
    store = EvidenceStore(tmp_path / "e.db")
    # Two acme snapshots with different content
    for content in ("first", "second"):
        p = ResearchPacket(query="x")
        p.envelopes.append(Envelope(
            content=content,
            source=Source(url="https://x/y", connector="s"),
        ))
        store.record_packet(p, tenant="acme")
    # A beta snapshot for the same URL but a stable hash
    p = ResearchPacket(query="x")
    p.envelopes.append(Envelope(
        content="beta-content", source=Source(url="https://x/y", connector="s"),
    ))
    store.record_packet(p, tenant="beta")
    # acme scope: sees the change
    acme_change = store.changed_since("https://x/y", tenant="acme")
    assert acme_change["changed"] is True
    # beta scope: only one snapshot => None
    beta_change = store.changed_since("https://x/y", tenant="beta")
    assert beta_change is None


# ---------------------------------------------------------------------------
# delete_tenant + export_tenant
# ---------------------------------------------------------------------------

def test_delete_tenant_fails_closed_without_confirm(tmp_path):
    store = EvidenceStore(tmp_path / "e.db")
    store.record_packet(_make_packet("a", ["https://a/1"]), tenant="acme")
    result = store.delete_tenant("acme")
    assert result["ok"] is False
    # Nothing removed
    assert store.stats(tenant="acme")["sources"] == 1


def test_delete_tenant_refuses_to_wipe_default(tmp_path):
    store = EvidenceStore(tmp_path / "e.db")
    store.record_packet(_make_packet("a", ["https://a/1"]))  # default tenant
    result = store.delete_tenant("default", confirm=True)
    assert result["ok"] is False
    assert "default" in result["reason"].lower()


def test_delete_tenant_removes_scoped_rows(tmp_path):
    store = EvidenceStore(tmp_path / "e.db")
    store.record_packet(_make_packet("a", ["https://a/1", "https://a/2"]),
                        tenant="acme")
    store.record_packet(_make_packet("b", ["https://b/1"]), tenant="beta")
    result = store.delete_tenant("acme", confirm=True)
    assert result["ok"] is True
    assert result["removed_sources"] == 2
    assert result["removed_packets"] == 1
    assert store.stats(tenant="acme")["sources"] == 0
    # Other tenant untouched
    assert store.stats(tenant="beta")["sources"] == 1


def test_export_tenant_returns_full_bundle(tmp_path):
    store = EvidenceStore(tmp_path / "e.db")
    store.record_packet(_make_packet("q1", ["https://a/1", "https://a/2"]),
                        tenant="acme")
    store.record_packet(_make_packet("q2", ["https://b/1"]), tenant="beta")
    export = store.export_tenant("acme")
    assert export["tenant"] == "acme"
    assert export["packet_count"] == 1
    assert len(export["packets"][0]["sources"]) == 2
    # Beta rows must not appear
    all_urls = [s["url"] for p in export["packets"] for s in p["sources"]]
    assert not any("https://b/" in u for u in all_urls)


# ---------------------------------------------------------------------------
# Schema migration — legacy DB (no tenant column) still works
# ---------------------------------------------------------------------------

def test_schema_migration_adds_tenant_to_legacy_db(tmp_path):
    """Create a DB with the pre-tenant schema, then let EvidenceStore
    open it — the migration must add tenant='default' to existing rows."""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE packets (id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE sources (id INTEGER PRIMARY KEY AUTOINCREMENT,
            packet_id INTEGER, url TEXT NOT NULL, connector TEXT, title TEXT,
            retrieved_at TEXT, content_hash TEXT, excerpt TEXT,
            FOREIGN KEY(packet_id) REFERENCES packets(id));
    """)
    conn.execute(
        "INSERT INTO packets(query, created_at) VALUES (?, ?)",
        ("legacy", "2020-01-01T00:00:00+00:00"),
    )
    pid = conn.execute("SELECT id FROM packets").fetchone()[0]
    conn.execute(
        "INSERT INTO sources(packet_id, url, connector, title) "
        "VALUES (?, 'https://legacy/x', 'seed', 'legacy-title')",
        (pid,),
    )
    conn.commit()
    conn.close()

    store = EvidenceStore(db_path)
    rows = store.query("legacy", tenant=None)
    assert len(rows) == 1
    assert rows[0]["tenant"] == "default"
    # Owner scope still works
    assert store.stats()["sources"] == 1
    # New tenant-scoped read for the default tenant matches
    default_rows = store.query("legacy", tenant="default")
    assert len(default_rows) == 1
