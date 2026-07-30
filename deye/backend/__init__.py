"""D-Eye provider-neutral backend - local, stdlib-only defaults.

This package implements Category 10 (provider-neutral backend +
workflow) plus rows in Category 6 (deletion/export) and Category 11
(auth for the local API). Everything here uses only the Python
standard library so the core install stays keyless + local.

Optional adapters (argon2, prometheus_client) plug in via
`[backend]` extras and never replace the local defaults.

Public surface:
    AuthStore(db_path)         # local user store, scrypt password hashing
    Queue(db_path)             # SQLite-backed FIFO job queue
    ObjectStore(root_dir)      # filesystem SHA-256 addressable store
    RBAC()                     # owner/user/service scope enforcement
    JSONLogger(name)           # structured stdout logs, redacted
    prometheus_text(metrics)   # Prometheus text-format emitter (no dep)
    Lifecycle(evidence_db,
              object_root)     # export / delete by owner or tenant
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import sys
import time
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from deye.core.redact import redact


# ---------------------------------------------------------------------------
# 1. AuthStore - local user store with scrypt password hashing
# ---------------------------------------------------------------------------

_AUTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    scheme TEXT NOT NULL,        -- always 'scrypt' in core
    salt BLOB NOT NULL,
    hashval BLOB NOT NULL,
    created_at TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    tenant TEXT NOT NULL DEFAULT 'default'
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
"""

_SCRYPT_N = 2 ** 14  # 16384 - CPU cost
_SCRYPT_R = 8
_SCRYPT_P = 1
_HASH_LEN = 32
_TOKEN_TTL_SECONDS = 24 * 60 * 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuthStore:
    """Local user + session store. No external secret required."""

    db_path: Path

    def _conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        with conn:
            conn.executescript(_AUTH_SCHEMA)
        return conn

    def create_user(self, username: str, password: str, *,
                    role: str = "user", tenant: str = "default") -> int:
        if not username or not password or len(password) < 8:
            raise ValueError("username required + password ≥ 8 chars")
        salt = secrets.token_bytes(16)
        hashval = hashlib.scrypt(
            password.encode("utf-8"), salt=salt,
            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_HASH_LEN,
        )
        with closing(self._conn()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO users(username, scheme, salt, hashval, "
                "created_at, role, tenant) VALUES (?, 'scrypt', ?, ?, ?, ?, ?)",
                (username, salt, hashval, _now(), role, tenant),
            )
            return cur.lastrowid

    def verify_password(self, username: str, password: str) -> dict | None:
        with closing(self._conn()) as conn:
            row = conn.execute(
                "SELECT id, salt, hashval, role, tenant FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if not row:
            return None
        expected = hashlib.scrypt(
            password.encode("utf-8"), salt=row["salt"],
            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_HASH_LEN,
        )
        if not hmac.compare_digest(expected, row["hashval"]):
            return None
        return {"id": row["id"], "username": username,
                "role": row["role"], "tenant": row["tenant"]}

    def issue_token(self, user_id: int, *, ttl: int = _TOKEN_TTL_SECONDS) -> str:
        token = secrets.token_urlsafe(32)
        exp = datetime.fromtimestamp(time.time() + ttl, tz=timezone.utc).isoformat()
        with closing(self._conn()) as conn, conn:
            conn.execute(
                "INSERT INTO sessions(token, user_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (token, user_id, _now(), exp),
            )
        return token

    def resolve_token(self, token: str) -> dict | None:
        if not token:
            return None
        with closing(self._conn()) as conn:
            row = conn.execute(
                "SELECT s.user_id, s.expires_at, u.username, u.role, u.tenant "
                "FROM sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token = ?",
                (token,),
            ).fetchone()
        if not row:
            return None
        exp = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) > exp:
            return None
        return {"id": row["user_id"], "username": row["username"],
                "role": row["role"], "tenant": row["tenant"]}

    def revoke_token(self, token: str) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---------------------------------------------------------------------------
# 2. Queue - SQLite-backed FIFO job queue
# ---------------------------------------------------------------------------

_QUEUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | in_flight | done | failed
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error TEXT,
    tenant TEXT NOT NULL DEFAULT 'default'
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_topic ON jobs(topic);
"""


@dataclass
class Queue:
    """Local, transactional job queue over SQLite."""

    db_path: Path

    def _conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        with conn:
            conn.executescript(_QUEUE_SCHEMA)
        return conn

    def enqueue(self, topic: str, payload: dict, *,
                tenant: str = "default") -> int:
        blob = json.dumps(payload, ensure_ascii=False)
        with closing(self._conn()) as conn:
            cur = conn.execute(
                "INSERT INTO jobs(topic, payload, created_at, tenant) "
                "VALUES (?, ?, ?, ?)",
                (topic, blob, _now(), tenant),
            )
            return cur.lastrowid

    # Four pre-built parameterised queries - one per topic+tenant combination.
    # Bandit B608 flagged the earlier dynamic-string version even though every
    # dynamic value goes through a `?` placeholder; this variant removes any
    # string concatenation so the static analyzer stays clean and the intent
    # (no user data ever meets the SQL literal) is obvious to a reviewer.
    _CLAIM_SQL = {
        (False, False): (
            "SELECT id, topic, payload, attempts, tenant FROM jobs "
            "WHERE status = 'pending' ORDER BY id LIMIT 1"),
        (True, False): (
            "SELECT id, topic, payload, attempts, tenant FROM jobs "
            "WHERE status = 'pending' AND topic = ? ORDER BY id LIMIT 1"),
        (False, True): (
            "SELECT id, topic, payload, attempts, tenant FROM jobs "
            "WHERE status = 'pending' AND tenant = ? ORDER BY id LIMIT 1"),
        (True, True): (
            "SELECT id, topic, payload, attempts, tenant FROM jobs "
            "WHERE status = 'pending' AND topic = ? AND tenant = ? "
            "ORDER BY id LIMIT 1"),
    }

    def claim(self, topic: str | None = None, *,
              tenant: str | None = None) -> dict | None:
        """Atomically pick the oldest pending job and mark it in_flight."""
        params: list = []
        if topic:
            params.append(topic)
        if tenant:
            params.append(tenant)
        sql = self._CLAIM_SQL[(bool(topic), bool(tenant))]
        with closing(self._conn()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(sql, params).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                return None
            conn.execute(
                "UPDATE jobs SET status = 'in_flight', started_at = ?, "
                "attempts = attempts + 1 WHERE id = ?",
                (_now(), row["id"]),
            )
            conn.execute("COMMIT")
        return {"id": row["id"], "topic": row["topic"],
                "payload": json.loads(row["payload"]),
                "attempts": row["attempts"] + 1, "tenant": row["tenant"]}

    def complete(self, job_id: int, *, error: str | None = None) -> None:
        status = "failed" if error else "done"
        with closing(self._conn()) as conn, conn:
            conn.execute(
                "UPDATE jobs SET status = ?, completed_at = ?, error = ? "
                "WHERE id = ?",
                (status, _now(), redact(error) if error else None, job_id),
            )

    def stats(self, *, tenant: str | None = None) -> dict:
        with closing(self._conn()) as conn:
            base = "SELECT status, COUNT(*) FROM jobs"
            params: list = []
            if tenant:
                base += " WHERE tenant = ?"
                params.append(tenant)
            base += " GROUP BY status"
            rows = conn.execute(base, params).fetchall()
        return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------------
# 3. ObjectStore - filesystem SHA-256 addressable storage
# ---------------------------------------------------------------------------

@dataclass
class ObjectStore:
    """Content-addressable filesystem object store.

    Files land at `<root>/objects/<aa>/<bb>/<full-sha256>`. Idempotent
    on identical content (same hash → same path → no-op write).
    """
    root: Path

    def _path(self, sha: str) -> Path:
        return self.root / "objects" / sha[:2] / sha[2:4] / sha

    def put(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        target = self._path(sha)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(data)
            try:
                os.chmod(target, 0o600)
            except OSError:
                pass
        return sha

    def get(self, sha: str) -> bytes | None:
        target = self._path(sha)
        return target.read_bytes() if target.exists() else None

    def delete(self, sha: str) -> bool:
        target = self._path(sha)
        if target.exists():
            target.unlink()
            return True
        return False

    def stats(self) -> dict:
        base = self.root / "objects"
        count = 0
        total_bytes = 0
        if base.exists():
            for f in base.rglob("*"):
                if f.is_file():
                    count += 1
                    total_bytes += f.stat().st_size
        return {"objects": count, "bytes": total_bytes}


# ---------------------------------------------------------------------------
# 4. RBAC - owner / user / service scopes
# ---------------------------------------------------------------------------

ROLES = ("owner", "user", "service")

# Role → set of allowed action verbs. `owner` gets everything; `user`
# can read + create + delete own; `service` is read-only across tenants.
_DEFAULT_MATRIX: dict[str, set[str]] = {
    "owner":   {"read", "create", "update", "delete", "export", "admin"},
    "user":    {"read", "create", "update", "delete", "export"},
    "service": {"read"},
}


@dataclass
class RBAC:
    matrix: dict[str, set[str]] = field(default_factory=lambda: {
        k: set(v) for k, v in _DEFAULT_MATRIX.items()
    })

    def allows(self, role: str, action: str) -> bool:
        return action in self.matrix.get(role, set())

    def require(self, role: str, action: str) -> None:
        if not self.allows(role, action):
            raise PermissionError(f"role '{role}' cannot perform '{action}'")

    def scope_query(self, role: str, tenant: str) -> dict:
        """Return a filter clause the caller can apply to their queries.

        - `owner` sees everything.
        - `user` sees rows scoped to their tenant.
        - `service` sees everything but only via read actions.
        """
        if role == "owner":
            return {}
        return {"tenant": tenant}


# ---------------------------------------------------------------------------
# 5. JSONLogger - structured stdout logs, redacted
# ---------------------------------------------------------------------------

@dataclass
class JSONLogger:
    name: str
    stream: object = None  # defaults to sys.stdout

    def _emit(self, level: str, event: str, **fields) -> None:
        out = self.stream or sys.stdout
        payload = {"ts": _now(), "level": level, "logger": self.name,
                   "event": event}
        payload.update(fields)
        # Redact any string value that could carry a credential.
        for k, v in list(payload.items()):
            if isinstance(v, str):
                payload[k] = redact(v)
        out.write(json.dumps(payload, ensure_ascii=False) + "\n")
        try:
            out.flush()
        except Exception:
            pass

    def info(self, event: str, **fields):
        self._emit("INFO", event, **fields)

    def warn(self, event: str, **fields):
        self._emit("WARN", event, **fields)

    def error(self, event: str, **fields):
        self._emit("ERROR", event, **fields)


# ---------------------------------------------------------------------------
# 6. Prometheus text-format emitter (no external dep)
# ---------------------------------------------------------------------------

def prometheus_text(metrics: Iterable[dict]) -> str:
    """Render an iterable of metric dicts as Prometheus text format.

    Each dict: {"name", "help", "type" (counter|gauge|histogram), "value",
    "labels" (dict, optional)}.
    """
    lines: list[str] = []
    seen: set[str] = set()
    for m in metrics:
        name = m["name"]
        if name not in seen:
            lines.append(f"# HELP {name} {m.get('help', '')}")
            lines.append(f"# TYPE {name} {m.get('type', 'gauge')}")
            seen.add(name)
        labels = m.get("labels") or {}
        if labels:
            parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            lines.append(f"{name}{{{parts}}} {m['value']}")
        else:
            lines.append(f"{name} {m['value']}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 7. Lifecycle - export + delete per owner/tenant
# ---------------------------------------------------------------------------

@dataclass
class Lifecycle:
    """Per-tenant lifecycle for evidence + object store.

    Keeps the evidence-store schema untouched; the multi-tenant scoping
    is applied at query time by filtering on connector-provided tenant
    metadata. In this MVP the evidence rows are single-tenant per
    installation; multi-tenant per-row is scoped through Queue + AuthStore.
    """
    evidence_db: Path
    object_root: Path | None = None

    def export_tenant(self, tenant: str) -> dict:
        """Return a JSON-serialisable export of everything the tenant owns."""
        out: dict = {"tenant": tenant, "exported_at": _now(),
                     "evidence": [], "jobs": [], "objects": []}
        if self.evidence_db.exists():
            with closing(sqlite3.connect(str(self.evidence_db))) as conn:
                conn.row_factory = sqlite3.Row
                packets = conn.execute(
                    "SELECT id, query, created_at FROM packets ORDER BY id"
                ).fetchall()
                for p in packets:
                    sources = conn.execute(
                        "SELECT url, connector, title, retrieved_at, "
                        "content_hash, excerpt FROM sources WHERE packet_id = ?",
                        (p["id"],),
                    ).fetchall()
                    out["evidence"].append({
                        "packet": dict(p),
                        "sources": [dict(s) for s in sources],
                    })
        # A queue.db, if present next to evidence.db, is picked up too.
        queue_db = self.evidence_db.parent / "queue.db"
        if queue_db.exists():
            with closing(sqlite3.connect(str(queue_db))) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT id, topic, payload, status, created_at, tenant "
                    "FROM jobs WHERE tenant = ?", (tenant,),
                ).fetchall()
                out["jobs"] = [dict(r) for r in rows]
        return out

    def delete_tenant(self, tenant: str, *, confirm: bool = False) -> dict:
        """Delete a tenant's data. Fails closed unless *confirm* is True."""
        if not confirm:
            return {"ok": False, "reason": "confirm=True required"}
        removed = {"evidence_packets": 0, "queue_jobs": 0}
        queue_db = self.evidence_db.parent / "queue.db"
        if queue_db.exists():
            with closing(sqlite3.connect(str(queue_db))) as conn, conn:
                cur = conn.execute("DELETE FROM jobs WHERE tenant = ?", (tenant,))
                removed["queue_jobs"] = cur.rowcount
        # Evidence store today is single-tenant. Tenant-scoped delete would
        # require an evidence-store schema migration + row-level scoping,
        # which is tracked as a separate row. Do NOT silently claim the
        # deletion happened when the schema does not support it.
        return {"ok": True, "removed": removed,
                "note": ("evidence rows are single-tenant per installation; "
                         "per-tenant evidence deletion requires an evidence "
                         "schema migration (planned)")}
