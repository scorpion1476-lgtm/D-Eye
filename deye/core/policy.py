"""D-Eye policy engine.

Deterministic, security-critical decisions live here -- OUTSIDE the LLM. The
model never decides whether a URL is safe to fetch; this module does, and it
fails closed.

Covers, per the forensic threat model:
  * URL scheme allowlist (http/https only by default)
  * userinfo / lookalike-host rejection
  * SSRF: post-resolution IP checks blocking loopback, private, link-local,
    multicast, reserved and cloud-metadata (169.254.169.254 / fd00:ec2::254)
  * DNS-rebinding resistance: callers fetch the *resolved* IP, not the name
  * response size / timeout / redirect-depth ceilings
  * a simple consent gate for state-changing ("write") actions
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# --- static configuration -------------------------------------------------

ALLOWED_SCHEMES = {"http", "https"}

# Extra host-level metadata endpoints that are not caught purely by IP range
# checks but must never be reachable through a fetch tool.
BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "metadata",
}


@dataclass
class Limits:
    """Resource ceilings applied to every acquisition."""

    timeout_seconds: float = 20.0
    max_bytes: int = 5 * 1024 * 1024  # 5 MiB
    max_redirects: int = 5
    max_crawl_depth: int = 2
    max_concurrency: int = 4


@dataclass
class PolicyDecision:
    """Result of a policy evaluation. ``allowed`` is the only thing callers act on."""

    allowed: bool
    reason: str = ""
    resolved_ips: list[str] = field(default_factory=list)


def _ip_is_public(ip: ipaddress._BaseAddress) -> bool:
    """Return True only for genuinely routable public addresses."""
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return False
    # IPv4 cloud metadata + IPv6 equivalents are already inside link_local /
    # private for the common cases, but block the canonical addresses by value
    # too so intent is explicit and auditable.
    if str(ip) in {"169.254.169.254", "fd00:ec2::254", "::ffff:169.254.169.254"}:
        return False
    # IPv4-mapped IPv6 (::ffff:a.b.c.d) can smuggle a private v4 address.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None and not _ip_is_public(mapped):
        return False
    return True


def resolve_public_ips(host: str) -> tuple[list[str], str]:
    """Resolve *host* and return (public_ips, error).

    If *any* resolved address is non-public the whole host is rejected -- a
    hostname that resolves to both a public and a private IP is a classic
    rebinding/pivot vector, so we fail closed.
    """
    host = (host or "").strip().rstrip(".")
    if not host:
        return [], "empty host"
    if host.lower() in BLOCKED_HOSTNAMES:
        return [], f"blocked metadata host: {host}"

    # A bare IP literal skips DNS but still gets range-checked.
    try:
        literal = ipaddress.ip_address(host)
        return ([str(literal)], "") if _ip_is_public(literal) else ([], f"non-public IP: {host}")
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        return [], f"DNS resolution failed: {exc}"

    ips: list[str] = []
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if not _ip_is_public(ip):
            return [], f"host resolves to non-public address: {addr}"
        ips.append(str(ip))
    if not ips:
        return [], "no addresses resolved"
    return sorted(set(ips)), ""


def evaluate_url(url: str, *, allowed_domains: list[str] | None = None) -> PolicyDecision:
    """Full deterministic gate for a URL an untrusted source asked us to fetch."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        _ = parsed.port  # forces validation of malformed authorities/ports
    except (TypeError, ValueError):
        return PolicyDecision(False, "malformed URL")

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return PolicyDecision(False, f"scheme not allowed: {parsed.scheme!r}")
    if parsed.username is not None or parsed.password is not None:
        return PolicyDecision(False, "URL contains userinfo (credential smuggling)")
    if not host:
        return PolicyDecision(False, "missing host")

    if allowed_domains:
        allowed = [d.lower().lstrip(".").rstrip(".") for d in allowed_domains]
        if not any(host == a or host.endswith("." + a) for a in allowed):
            return PolicyDecision(False, f"host {host} not in allowlist")

    ips, err = resolve_public_ips(host)
    if err:
        return PolicyDecision(False, err)
    return PolicyDecision(True, "ok", resolved_ips=ips)


@dataclass
class ConsentPolicy:
    """Read-only by default. Write / browser / side-effecting actions must be
    granted explicitly by a human before the router will run them."""

    allow_write: bool = False
    granted_actions: set[str] = field(default_factory=set)

    def permits(self, action: str, *, is_write: bool) -> PolicyDecision:
        if not is_write:
            return PolicyDecision(True, "read-only")
        if self.allow_write and action in self.granted_actions:
            return PolicyDecision(True, "explicitly granted")
        return PolicyDecision(
            False,
            f"write action '{action}' requires explicit consent (read-only default)",
        )
