"""Persistent evidence store (SQLite) with per-tenant scoping.

This is what distinguishes *temporary per-run packets* (the Markdown/JSON files
`research` writes) from *persistent evidence* (queryable across runs). It backs
the `query_evidence` MCP tool and the `deye evidence` CLI command, and provides
URL+content-hash deduplication and simple source-change detection.

Multi-tenant model
------------------
Every packet + source carries a `tenant` column (default: "default"). The
scoping is applied at query time; a tenant-scoped caller sees only their own
rows. An owner scope sees everything.

Migration: on connection we ensure the `tenant` column exists on both tables;
if a legacy schema is present, the column is added with default "default".
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from deye.core.provenance import ResearchPacket, content_hash

# Base schema — creates tables + tenant-agnostic indexes only. Tenant-
# touching indexes are created AFTER the migration adds the column to any
# legacy DB (otherwise opening a legacy DB throws "no such column: tenant"
# at the CREATE INDEX step).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS packets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tenant TEXT NOT NULL DEFAULT 'default'
);
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    packet_id INTEGER,
    url TEXT NOT NULL,
    connector TEXT,
    title TEXT,
    retrieved_at TEXT,
    content_hash TEXT,
    excerpt TEXT,
    tenant TEXT NOT NULL DEFAULT 'default',
    FOREIGN KEY(packet_id) REFERENCES packets(id)
);
CREATE INDEX IF NOT EXISTS idx_sources_url ON sources(url);
CREATE INDEX IF NOT EXISTS idx_sources_hash ON sources(content_hash);
"""

_TENANT_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_sources_tenant ON sources(tenant);
CREATE INDEX IF NOT EXISTS idx_packets_tenant ON packets(tenant);
"""


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column
               for row in conn.execute(f'PRAGMA table_info("{table}")'))


def _migrate_add_tenant(conn: sqlite3.Connection) -> None:
    """Add tenant column to legacy tables (packets, sources) if missing."""
    for table in ("packets", "sources"):
        if not _column_exists(conn, table, "tenant"):
            conn.execute(
                f'ALTER TABLE "{table}" ADD COLUMN tenant TEXT NOT NULL DEFAULT \'default\''
            )


@dataclass
class EvidenceStore:
    db_path: Path

    def _conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        with conn:
            conn.executescript(_SCHEMA)
            _migrate_add_tenant(conn)
            conn.executescript(_TENANT_INDEXES)
        return conn

    def record_packet(self, packet: ResearchPacket, *,
                      tenant: str = "default") -> int:
        with closing(self._conn()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO packets(query, created_at, tenant) VALUES (?, ?, ?)",
                (packet.query, packet.created_at, tenant),
            )
            packet_id = cur.lastrowid
            for env in packet.envelopes:
                conn.execute(
                    "INSERT INTO sources(packet_id, url, connector, title, retrieved_at, "
                    "content_hash, excerpt, tenant) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        packet_id, env.source.url, env.source.connector, env.source.title,
                        env.source.retrieved_at, content_hash(env.content),
                        (env.content or "")[:500], tenant,
                    ),
                )
            return packet_id

    # Four pre-built parameterised queries — mirrors the Queue.claim pattern
    # so bandit's B608 stays clean. Keys are (has_query, scoped_to_tenant).
    _QUERY_SQL = {
        (False, False): (
            "SELECT url, connector, title, retrieved_at, content_hash, excerpt, tenant "
            "FROM sources ORDER BY id DESC LIMIT ?"),
        (True, False): (
            "SELECT url, connector, title, retrieved_at, content_hash, excerpt, tenant "
            "FROM sources WHERE url LIKE ? OR title LIKE ? OR excerpt LIKE ? "
            "ORDER BY id DESC LIMIT ?"),
        (False, True): (
            "SELECT url, connector, title, retrieved_at, content_hash, excerpt, tenant "
            "FROM sources WHERE tenant = ? ORDER BY id DESC LIMIT ?"),
        (True, True): (
            "SELECT url, connector, title, retrieved_at, content_hash, excerpt, tenant "
            "FROM sources WHERE tenant = ? AND "
            "(url LIKE ? OR title LIKE ? OR excerpt LIKE ?) "
            "ORDER BY id DESC LIMIT ?"),
    }

    def query(self, text: str, *, limit: int = 20,
              tenant: str | None = None) -> list[dict]:
        """Text search over the sources table.

        When *tenant* is None the caller sees every row (owner scope).
        Otherwise only rows for the given tenant are returned.
        """
        has_query = bool(text)
        scoped = tenant is not None
        sql = self._QUERY_SQL[(has_query, scoped)]
        params: list = []
        if scoped:
            params.append(tenant)
        if has_query:
            like = f"%{text}%"
            params.extend([like, like, like])
        params.append(limit)
        with closing(self._conn()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def changed_since(self, url: str, *,
                      tenant: str | None = None) -> dict | None:
        """Return change info if the same URL was seen with a different hash."""
        if tenant is None:
            sql = ("SELECT content_hash, retrieved_at FROM sources "
                   "WHERE url = ? ORDER BY id DESC LIMIT 2")
            params: list = [url]
        else:
            sql = ("SELECT content_hash, retrieved_at FROM sources "
                   "WHERE url = ? AND tenant = ? ORDER BY id DESC LIMIT 2")
            params = [url, tenant]
        with closing(self._conn()) as conn:
            rows = conn.execute(sql, params).fetchall()
        if len(rows) < 2:
            return None
        if rows[0]["content_hash"] != rows[1]["content_hash"]:
            return {"url": url, "changed": True,
                    "latest": rows[0]["content_hash"], "previous": rows[1]["content_hash"]}
        return {"url": url, "changed": False}

    def stats(self, *, tenant: str | None = None) -> dict:
        if tenant is None:
            sql_p = "SELECT COUNT(*) FROM packets"
            sql_s = "SELECT COUNT(*) FROM sources"
            sql_d = "SELECT COUNT(DISTINCT url) FROM sources"
            params_p: list = []
            params_s: list = []
        else:
            sql_p = "SELECT COUNT(*) FROM packets WHERE tenant = ?"
            sql_s = "SELECT COUNT(*) FROM sources WHERE tenant = ?"
            sql_d = "SELECT COUNT(DISTINCT url) FROM sources WHERE tenant = ?"
            params_p = [tenant]
            params_s = [tenant]
        with closing(self._conn()) as conn:
            packets = conn.execute(sql_p, params_p).fetchone()[0]
            sources = conn.execute(sql_s, params_s).fetchone()[0]
            distinct = conn.execute(sql_d, params_s).fetchone()[0]
        return {"packets": packets, "sources": sources,
                "distinct_urls": distinct}

    def delete_tenant(self, tenant: str, *, confirm: bool = False) -> dict:
        """Delete every packet + source row for a given tenant.

        Fails closed unless *confirm=True* and *tenant* != 'default'
        (owner data is not deleted by tenant-scope calls)."""
        if not confirm:
            return {"ok": False, "reason": "confirm=True required"}
        if tenant == "default":
            return {"ok": False,
                    "reason": "refuse to delete the default (owner) tenant"}
        with closing(self._conn()) as conn, conn:
            src = conn.execute("DELETE FROM sources WHERE tenant = ?",
                               (tenant,)).rowcount
            pkt = conn.execute("DELETE FROM packets WHERE tenant = ?",
                               (tenant,)).rowcount
        return {"ok": True, "removed_sources": src, "removed_packets": pkt}

    def export_tenant(self, tenant: str) -> dict:
        """Return a JSON-serialisable bundle of everything the tenant owns."""
        with closing(self._conn()) as conn:
            packets = [dict(r) for r in conn.execute(
                "SELECT id, query, created_at, tenant FROM packets "
                "WHERE tenant = ? ORDER BY id", (tenant,),
            ).fetchall()]
            per_packet: list[dict] = []
            for p in packets:
                sources = [dict(r) for r in conn.execute(
                    "SELECT url, connector, title, retrieved_at, "
                    "content_hash, excerpt, tenant FROM sources "
                    "WHERE packet_id = ? AND tenant = ?",
                    (p["id"], tenant),
                ).fetchall()]
                per_packet.append({"packet": p, "sources": sources})
        return {"tenant": tenant, "packets": per_packet,
                "packet_count": len(per_packet)}
