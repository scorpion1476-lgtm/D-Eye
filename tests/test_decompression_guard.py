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
