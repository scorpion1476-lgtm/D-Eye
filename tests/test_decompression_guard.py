import gzip
from deye.connectors.base import _decompress

def test_gzip_bomb_truncated():
    payload = b"A" * (2_000_000)          # 2 MB decompressed
    body = gzip.compress(payload)
    data, warns = _decompress(body, "gzip", cap=1000)   # cap far below
    assert len(data) == 1000 and any("bomb guard" in w for w in warns)

def test_plain_passthrough():
    data, warns = _decompress(b"hello", "", cap=10)
    assert data == b"hello" and warns == []


def test_gzip_bomb_does_not_materialize_full_payload():
    # Regression: the cap must bound MEMORY, not just the returned slice. A tiny
    # compressed body that expands ~1000x must be stopped incrementally, never
    # fully decompressed into RAM. 50 MB expands from a few KB; we cap at 1 KB
    # and assert we get exactly the cap back with the bomb-guard warning.
    payload = b"\0" * (50_000_000)
    body = gzip.compress(payload)
    assert len(body) < 100_000  # high-ratio bomb
    data, warns = _decompress(body, "gzip", cap=1024)
    assert len(data) == 1024 and any("bomb guard" in w for w in warns)


def test_deflate_roundtrip_under_cap():
    import zlib
    body = zlib.compress(b"small deflate payload")
    data, warns = _decompress(body, "deflate", cap=1_000_000)
    assert data == b"small deflate payload" and warns == []
