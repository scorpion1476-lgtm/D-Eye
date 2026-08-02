"""C10 provider-neutral backend, verified through the shipped `deye backend`
CLI surface (not just the in-process classes).

Covered rows:
  C10-F001 Managed authentication  - local scrypt user store + verify
  C10-F002 Serverless functions    - SQLite FIFO queue enqueue/claim
  C10-F003 Document/metadata store - object store put/get (+ EvidenceStore)
  C10-F004 Object storage          - content-addressable SHA-256 store
  C10-F006 Secret management        - reference resolution, value never printed

Everything is local, keyless, and offline: SQLite + files under DEYE_HOME.
"""
from __future__ import annotations

import json

import pytest

from deye.cli import main


def _run(capsys, argv) -> dict:
    rc = main(argv)
    out = capsys.readouterr().out
    return {"rc": rc, "out": out, "json": json.loads(out.split("---")[0])}


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("DEYE_HOME", str(tmp_path))
    return tmp_path


# -- C10-F001 auth ----------------------------------------------------------

def test_auth_add_user_and_verify(home, monkeypatch, capsys):
    monkeypatch.setenv("DEYE_BACKEND_PASSWORD", "correcthorse")
    created = _run(capsys, ["backend", "auth", "add-user", "bob", "--role", "user"])
    assert created["json"]["created"] is True and created["json"]["user_id"] >= 1

    ok = _run(capsys, ["backend", "auth", "verify", "bob"])
    assert ok["json"]["authenticated"] is True and ok["json"]["role"] == "user"

    monkeypatch.setenv("DEYE_BACKEND_PASSWORD", "wrongpassword")
    bad = _run(capsys, ["backend", "auth", "verify", "bob"])
    assert bad["json"]["authenticated"] is False


def test_auth_stores_no_plaintext_password(home, monkeypatch, capsys):
    monkeypatch.setenv("DEYE_BACKEND_PASSWORD", "s3cr3t-passphrase")
    _run(capsys, ["backend", "auth", "add-user", "carol"])
    blob = (home / "auth.db").read_bytes()
    assert b"s3cr3t-passphrase" not in blob          # password never stored in clear


# -- C10-F002 queue ---------------------------------------------------------

def test_queue_enqueue_then_claim(home, capsys):
    enq = _run(capsys, ["backend", "queue", "enqueue", "crawl", '{"url": "https://x"}'])
    assert enq["json"]["enqueued"] is True
    claim = _run(capsys, ["backend", "queue", "claim"])
    assert claim["json"]["topic"] == "crawl"
    assert claim["json"]["payload"] == {"url": "https://x"}
    # queue is now empty
    empty = _run(capsys, ["backend", "queue", "claim"])
    assert empty["json"] == {"claimed": False}


# -- C10-F003/F004 object store --------------------------------------------

def test_object_put_get_is_content_addressable(home, tmp_path, capsys):
    f = tmp_path / "blob.bin"
    f.write_bytes(b"deye object bytes")
    put = _run(capsys, ["backend", "object", "put", str(f)])
    sha = put["json"]["sha256"]
    assert len(sha) == 64
    # same content -> same address (idempotent)
    put2 = _run(capsys, ["backend", "object", "put", str(f)])
    assert put2["json"]["sha256"] == sha
    # retrieve round-trips the exact bytes
    out = tmp_path / "out.bin"
    got = _run(capsys, ["backend", "object", "get", sha, "-o", str(out)])
    assert got["json"]["found"] is True
    assert out.read_bytes() == b"deye object bytes"


# -- C10-F006 secret management --------------------------------------------

def test_secret_check_resolves_reference_without_printing_value(home, monkeypatch, capsys):
    monkeypatch.setenv("DEYE_DEMO_TOKEN", "tok-should-not-appear")
    present = _run(capsys, ["backend", "secret", "check", "env:DEYE_DEMO_TOKEN"])
    assert present["json"]["resolves"] is True
    assert "tok-should-not-appear" not in present["out"]      # value never surfaced

    monkeypatch.delenv("DEYE_UNSET_TOKEN", raising=False)
    absent = _run(capsys, ["backend", "secret", "check", "env:DEYE_UNSET_TOKEN"])
    assert absent["json"]["resolves"] is False
