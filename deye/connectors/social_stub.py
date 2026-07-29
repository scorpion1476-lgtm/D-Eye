"""Lawful boundary declarations for social platforms that D-Eye deliberately
does not scrape.

Each entry surfaces as a `ConnectorManifest` with a `health()` that reports
`missing` and a `run()` that raises with a clear, product-neutral reason.
The router will skip these unless a real replacement adapter is registered
(e.g. a Twitter/X API v2 adapter behind an opt-in extra); the row is not
silently dropped from the catalogue.

Never bypass a platform's authentication, rate-limits, CAPTCHAs, or ToS to
provide these capabilities. Where a lawful keyless read-only surface exists
(RSS, oEmbed, self-hosted RSS-Bridge), a dedicated connector should be added
instead of this stub.
"""
from __future__ import annotations

from deye.connectors.base import ConnectorError
from deye.core.config import Config
from deye.core.provenance import Envelope
from deye.core.registry import ConnectorManifest, HealthReport


PLATFORM_BOUNDARIES: dict[str, str] = {
    "twitter_x": (
        "Twitter/X has deprecated its free read-only API and rate-limits "
        "unauthenticated scraping. Lawful FOSS-only read access is not "
        "generally available; a paid X API v2 key would be required behind "
        "an opt-in extras adapter (never a mandatory dependency)."
    ),
    "linkedin": (
        "LinkedIn's ToS prohibit unauthenticated scraping. Their API "
        "requires an approved application, oauth flow, and account. No "
        "lawful FOSS-only read path exists."
    ),
    "facebook": (
        "Facebook requires a Meta developer account + Graph API tokens for "
        "programmatic reads. Public-page RSS was retired. No lawful "
        "keyless read path."
    ),
    "instagram": (
        "Instagram requires a Meta Instagram Basic Display / Graph API "
        "token. Web scraping is rate-limited and against ToS. No lawful "
        "keyless read path."
    ),
    "bilibili": (
        "Bilibili does not expose a documented keyless public API for "
        "general search. Anonymous scraping breaches their ToS. A community "
        "reverse-engineered client could be shipped as an opt-in adapter."
    ),
    "xiaohongshu": (
        "Xiaohongshu offers no documented public API. Web scraping breaches "
        "their ToS. No lawful FOSS-only path."
    ),
}


def _make_stub_class(name: str, reason: str):
    class StubConnector:
        __qualname__ = name
        # class-level attributes match the protocol
        is_write = False

        def __init__(self, config: Config | None = None):
            self.config = config or Config()
            self.name = name
            self.capability = "search"

        def health(self) -> HealthReport:
            return HealthReport(
                connector=name, status="missing", detail=reason,
            )

        def run(self, request: dict) -> Envelope:
            raise ConnectorError(f"{name}: {reason}")

    StubConnector.__name__ = f"{name}_stub"
    return StubConnector


def manifests(config: Config | None = None) -> list[ConnectorManifest]:
    out: list[ConnectorManifest] = []
    for name, reason in PLATFORM_BOUNDARIES.items():
        cls = _make_stub_class(name, reason)
        out.append(ConnectorManifest(
            name=name, capability="search",
            license="documentation",
            requires_credentials=True,
            requires_network=True,
            cost="paid",
            preference=999,  # last-resort; router prefers real connectors
            origin="platform_gated",
            factory=(lambda c=cls: c(config)),
        ))
    return out
