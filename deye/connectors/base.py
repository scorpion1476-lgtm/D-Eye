"""Shared connector helpers.

Security-critical fetch path. Unlike the v0.1 fetch (which validated a URL and
then let urllib re-resolve DNS -- a TOCTOU/rebinding gap), this version:

  * resolves + range-checks the host ONCE via the policy engine, then
  * PINS the TCP connection to the vetted IP (the socket connects to that exact
    address; the hostname cannot rebind to a private IP between check and
    connect), while
  * preserving the real hostname for TLS SNI + certificate validation,
  * enforcing a raw size cap AND a decompressed size cap (gzip/deflate bomb
    protection), and
  * re-evaluating every redirect hop through the policy engine.
"""

from __future__ import annotations

import gzip
import http.client
import socket
import ssl
import time
import urllib.parse
import zlib

from deye.core.policy import Limits, evaluate_url
from deye.core.registry import HealthReport


class ConnectorError(RuntimeError):
    pass


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, pinned_ip: str, **kw):
        super().__init__(host, **kw)
        self._pinned_ip = pinned_ip

    def connect(self):  # connect to the vetted IP, not a fresh DNS lookup
        self.sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, pinned_ip: str, *, context: ssl.SSLContext, **kw):
        super().__init__(host, context=context, **kw)
        self._pinned_ip = pinned_ip

    def connect(self):
        raw = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        # server_hostname = the REAL host -> correct SNI + cert validation,
        # even though the TCP peer is the pinned IP.
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def _decompress(body: bytes, encoding: str, cap: int) -> tuple[bytes, list[str]]:
    enc = (encoding or "").lower()
    try:
        if enc == "gzip":
            data = gzip.decompress(body)
        elif enc in ("deflate", "zlib"):
            data = zlib.decompress(body)
        else:
            return body, []
    except Exception as exc:  # noqa: BLE001
        return body, [f"decompression failed ({enc}): {exc}"]
    if len(data) > cap:
        return data[:cap], ["decompressed body exceeded cap; truncated (bomb guard)"]
    return data, []


def _one_hop(url: str, limits: Limits, allowed_domains) -> tuple[int, dict, bytes]:
    decision = evaluate_url(url, allowed_domains=allowed_domains)
    if not decision.allowed:
        raise ConnectorError(f"blocked by policy: {decision.reason}")
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
    headers = {
        "Host": host if port in (80, 443) else f"{host}:{port}",
        "User-Agent": "D-Eye/0.2 (+https://example.invalid/deye)",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
    }
    last_err = ""
    for pinned_ip in decision.resolved_ips:
        try:
            if parts.scheme == "https":
                ctx = ssl.create_default_context()
                conn = _PinnedHTTPSConnection(host, pinned_ip, context=ctx,
                                              port=port, timeout=limits.timeout_seconds)
            else:
                conn = _PinnedHTTPConnection(host, pinned_ip, port=port,
                                             timeout=limits.timeout_seconds)
            conn.request("GET", path, headers=headers)
            resp = conn.getresponse()
            raw = resp.read(limits.max_bytes + 1)
            resp_headers = {k.lower(): v for k, v in resp.getheaders()}
            conn.close()
            return resp.status, resp_headers, raw
        except ConnectorError:
            raise
        except Exception as exc:  # noqa: BLE001 -- try next pinned IP
            last_err = str(exc)
            continue
    raise ConnectorError(f"connection failed: {last_err or 'no resolved IPs'}")


def safe_get(url: str, *, limits: Limits, allowed_domains=None) -> tuple[bytes, str, list[str]]:
    """Policy-gated, connection-pinned HTTP GET. Returns (body, final_url, warnings)."""
    warnings: list[str] = []
    current = url
    for _ in range(limits.max_redirects + 1):
        status, headers, raw = _one_hop(current, limits, allowed_domains)
        if status in (301, 302, 303, 307, 308):
            location = headers.get("location")
            if not location:
                raise ConnectorError("redirect without Location")
            current = urllib.parse.urljoin(current, location)
            warnings.append(f"redirect -> {current}")
            continue
        if len(raw) > limits.max_bytes:
            raw = raw[: limits.max_bytes]
            warnings.append("response truncated at size limit")
        body, dw = _decompress(raw, headers.get("content-encoding", ""), limits.max_bytes)
        warnings.extend(dw)
        ctype = headers.get("content-type", "")
        if ctype and not any(t in ctype for t in ("text/", "json", "xml", "html")):
            warnings.append(f"non-text content-type: {ctype}")
        return body, current, warnings
    raise ConnectorError("too many redirects")


def timed_health(check) -> HealthReport:
    start = time.monotonic()
    report = check()
    report.latency_ms = round((time.monotonic() - start) * 1000, 1)
    return report
