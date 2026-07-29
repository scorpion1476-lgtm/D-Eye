"""Acceptance tests for `deye.backend` — local auth / queue / storage /
RBAC / observability / lifecycle.

Covers Category 10 rows (managed authentication, queue-driven workflows,
document + object storage, secret management adjacency via redaction,
observability, RBAC, deletion + data export) and their Category 6
neighbours (deletion + export).

All tests are stdlib-only. No external services. No network.
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import pytest

from deye.backend import (
    AuthStore, JSONLogger, Lifecycle, ObjectStore, Queue, RBAC,
    prometheus_text,
)


# ---------------------------------------------------------------------------
# AuthStore
# ---------------------------------------------------------------------------

def test_auth_create_and_verify(tmp_path):
    a = AuthStore(tmp_path / "auth.db")
    uid = a.create_user("alice", "aVeryLongPassword", role="user", tenant="acme")
    assert isinstance(uid, int)
    verified = a.verify_password("alice", "aVeryLongPassword")
    assert verified["username"] == "alice"
    assert verified["role"] == "user"
    assert verified["tenant"] == "acme"
    # wrong password
    assert a.verify_password("alice", "nope") is None
    # missing user
    assert a.verify_password("bob", "aVeryLongPassword") is None


def test_auth_rejects_short_password(tmp_path):
    a = AuthStore(tmp_path / "auth.db")
    with pytest.raises(ValueError):
        a.create_user("alice", "short")


def test_auth_token_lifecycle(tmp_path):
    a = AuthStore(tmp_path / "auth.db")
    uid = a.create_user("alice", "aVeryLongPassword")
    tok = a.issue_token(uid, ttl=60)
    who = a.resolve_token(tok)
    assert who["id"] == uid
    a.revoke_token(tok)
    assert a.resolve_token(tok) is None


def test_auth_expired_token_returns_none(tmp_path):
    a = AuthStore(tmp_path / "auth.db")
    uid = a.create_user("alice", "aVeryLongPassword")
    tok = a.issue_token(uid, ttl=-1)  # already expired
    assert a.resolve_token(tok) is None


def test_auth_password_hashing_uses_unique_salts(tmp_path):
    """Same password → different stored hashes (salt is unique per user)."""
    a = AuthStore(tmp_path / "auth.db")
    a.create_user("alice", "sharedPassword1")
    a.create_user("bob", "sharedPassword1")
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "auth.db"))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT username, salt, hashval FROM users").fetchall()
    conn.close()
    assert rows[0]["salt"] != rows[1]["salt"]
    assert rows[0]["hashval"] != rows[1]["hashval"]


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

def test_queue_enqueue_and_claim(tmp_path):
    q = Queue(tmp_path / "q.db")
    jid = q.enqueue("crawl", {"url": "https://example.com"}, tenant="acme")
    claim = q.claim(topic="crawl", tenant="acme")
    assert claim is not None
    assert claim["id"] == jid
    assert claim["topic"] == "crawl"
    assert claim["payload"]["url"] == "https://example.com"
    assert claim["attempts"] == 1
    # nothing left
    assert q.claim(topic="crawl", tenant="acme") is None
    q.complete(jid)
    stats = q.stats(tenant="acme")
    assert stats.get("done") == 1


def test_queue_isolates_tenants(tmp_path):
    q = Queue(tmp_path / "q.db")
    q.enqueue("crawl", {"n": 1}, tenant="acme")
    q.enqueue("crawl", {"n": 2}, tenant="beta")
    assert q.claim(tenant="acme")["payload"]["n"] == 1
    assert q.claim(tenant="acme") is None
    assert q.claim(tenant="beta")["payload"]["n"] == 2


def test_queue_records_failure_with_redaction(tmp_path):
    q = Queue(tmp_path / "q.db")
    jid = q.enqueue("t", {})
    q.claim()
    # complete with an error that contains a bearer token; redact must scrub it
    q.complete(jid, error="Bearer sk-user_1234567890ABCDEFGH failed")
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "q.db"))
    row = conn.execute("SELECT status, error FROM jobs WHERE id = ?", (jid,)).fetchone()
    conn.close()
    assert row[0] == "failed"
    assert "REDACTED" in row[1]
    assert "1234567890" not in row[1]


# ---------------------------------------------------------------------------
# ObjectStore
# ---------------------------------------------------------------------------

def test_object_store_content_addressable_roundtrip(tmp_path):
    store = ObjectStore(tmp_path / "obj")
    payload = b"hello D-Eye"
    sha = store.put(payload)
    assert len(sha) == 64
    # idempotent — same content = same sha, no error
    assert store.put(payload) == sha
    assert store.get(sha) == payload
    stats = store.stats()
    assert stats["objects"] == 1
    assert stats["bytes"] == len(payload)


def test_object_store_delete(tmp_path):
    store = ObjectStore(tmp_path / "obj")
    sha = store.put(b"x")
    assert store.delete(sha) is True
    assert store.get(sha) is None
    assert store.delete(sha) is False


def test_object_store_shards_by_hash(tmp_path):
    store = ObjectStore(tmp_path / "obj")
    sha = store.put(b"payload")
    # File path uses first-2 / next-2 shard
    expected = tmp_path / "obj" / "objects" / sha[:2] / sha[2:4] / sha
    assert expected.exists()


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

def test_rbac_default_matrix():
    r = RBAC()
    assert r.allows("owner", "delete")
    assert r.allows("owner", "admin")
    assert r.allows("user", "read")
    assert r.allows("user", "create")
    assert not r.allows("user", "admin")
    assert r.allows("service", "read")
    assert not r.allows("service", "create")
    assert not r.allows("service", "delete")


def test_rbac_require_raises_on_denied():
    r = RBAC()
    r.require("user", "read")  # ok
    with pytest.raises(PermissionError):
        r.require("service", "delete")


def test_rbac_scope_query_owner_sees_all():
    r = RBAC()
    assert r.scope_query("owner", "acme") == {}
    assert r.scope_query("user", "acme") == {"tenant": "acme"}
    assert r.scope_query("service", "beta") == {"tenant": "beta"}


# ---------------------------------------------------------------------------
# JSONLogger
# ---------------------------------------------------------------------------

def test_json_logger_writes_structured_line_with_redaction():
    buf = io.StringIO()
    log = JSONLogger("test", stream=buf)
    log.info("request", user="alice", note="Bearer sk-user_1234567890ABCDEFGH")
    line = buf.getvalue().splitlines()[0]
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["event"] == "request"
    assert payload["user"] == "alice"
    # redact should have scrubbed the bearer token
    assert "REDACTED" in payload["note"]


def test_json_logger_error_and_warn():
    buf = io.StringIO()
    log = JSONLogger("t", stream=buf)
    log.warn("w"); log.error("e")
    lines = [json.loads(l) for l in buf.getvalue().splitlines()]
    assert lines[0]["level"] == "WARN"
    assert lines[1]["level"] == "ERROR"


# ---------------------------------------------------------------------------
# Prometheus text emitter
# ---------------------------------------------------------------------------

def test_prometheus_text_shape():
    text = prometheus_text([
        {"name": "deye_requests_total", "help": "total requests",
         "type": "counter", "value": 12, "labels": {"route": "search"}},
        {"name": "deye_requests_total", "value": 5, "labels": {"route": "fetch"}},
        {"name": "deye_up", "help": "server up", "type": "gauge", "value": 1},
    ])
    # HELP + TYPE appear once per metric
    assert text.count("# HELP deye_requests_total") == 1
    assert "# TYPE deye_requests_total counter" in text
    assert 'deye_requests_total{route="search"} 12' in text
    assert 'deye_requests_total{route="fetch"} 5' in text
    assert "deye_up 1" in text


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def test_lifecycle_export_and_delete(tmp_path):
    # seed a queue + evidence store; make sure export sees both
    from deye.core.evidence import EvidenceStore
    from deye.core.provenance import Envelope, ResearchPacket, Source

    home = tmp_path / "home"
    home.mkdir()
    ev = EvidenceStore(home / "evidence.db")
    packet = ResearchPacket(query="hello")
    packet.envelopes.append(Envelope(
        content="content", source=Source(url="https://x", connector="test"),
    ))
    ev.record_packet(packet)

    q = Queue(home / "queue.db")
    q.enqueue("crawl", {"n": 1}, tenant="acme")

    lc = Lifecycle(evidence_db=home / "evidence.db")
    export = lc.export_tenant("acme")
    assert export["tenant"] == "acme"
    assert len(export["evidence"]) >= 1
    assert len(export["jobs"]) == 1

    # delete without confirm fails closed
    result = lc.delete_tenant("acme")
    assert result["ok"] is False

    # delete with confirm removes queue rows (evidence rows are single-tenant)
    result = lc.delete_tenant("acme", confirm=True)
    assert result["ok"] is True
    assert result["removed"]["queue_jobs"] == 1
    # note field explains the multi-tenant evidence limitation
    assert "single-tenant" in result["note"]
