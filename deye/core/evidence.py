"""Persistent evidence store (SQLite).

This is what distinguishes *temporary per-run packets* (the Markdown/JSON files
`research` writes) from *persistent evidence* (queryable across runs). It backs
the `query_evidence` MCP tool and the `deye evidence` CLI command, and provides
URL+content-hash deduplication and simple source-change detection.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from deye.core.provenance import ResearchPacket, content_hash

_SCHEMA = """
CREATE TABLE IF NOT EXISTS packets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    created_at TEXT NOT NULL
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
    FOREIGN KEY(packet_id) REFERENCES packets(id)
);
CREATE INDEX IF NOT EXISTS idx_sources_url ON sources(url);
CREATE INDEX IF NOT EXISTS idx_sources_hash ON sources(content_hash);
"""


@dataclass
class EvidenceStore:
    db_path: Path

    def _conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        with conn:
            conn.executescript(_SCHEMA)
        return conn

    def record_packet(self, packet: ResearchPacket) -> int:
        with closing(self._conn()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO packets(query, created_at) VALUES (?, ?)",
                (packet.query, packet.created_at),
            )
            packet_id = cur.lastrowid
            for env in packet.envelopes:
                conn.execute(
                    "INSERT INTO sources(packet_id, url, connector, title, retrieved_at, "
                    "content_hash, excerpt) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        packet_id, env.source.url, env.source.connector, env.source.title,
                        env.source.retrieved_at, content_hash(env.content),
                        (env.content or "")[:500],
                    ),
                )
            return packet_id

    def query(self, text: str, *, limit: int = 20) -> list[dict]:
        like = f"%{text}%"
        with closing(self._conn()) as conn:
            rows = conn.execute(
                "SELECT url, connector, title, retrieved_at, content_hash, excerpt "
                "FROM sources WHERE url LIKE ? OR title LIKE ? OR excerpt LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (like, like, like, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def changed_since(self, url: str) -> dict | None:
        """Return change info if the same URL was seen with a different hash."""
        with closing(self._conn()) as conn:
            rows = conn.execute(
                "SELECT content_hash, retrieved_at FROM sources WHERE url = ? "
                "ORDER BY id DESC LIMIT 2",
                (url,),
            ).fetchall()
        if len(rows) < 2:
            return None
        if rows[0]["content_hash"] != rows[1]["content_hash"]:
            return {"url": url, "changed": True,
                    "latest": rows[0]["content_hash"], "previous": rows[1]["content_hash"]}
        return {"url": url, "changed": False}

    def stats(self) -> dict:
        with closing(self._conn()) as conn:
            packets = conn.execute("SELECT COUNT(*) FROM packets").fetchone()[0]
            sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            distinct = conn.execute("SELECT COUNT(DISTINCT url) FROM sources").fetchone()[0]
        return {"packets": packets, "sources": sources, "distinct_urls": distinct}
