"""Capability registry + connector manifests.

Routing is capability-oriented, not platform-oriented (forensic 3.2): a caller
asks for ``search`` / ``fetch`` / ``extract`` / ``feed`` / ``repo.inspect`` and
the registry knows which connectors can satisfy it, in preference order.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from deye.core.provenance import Envelope


class Connector(Protocol):
    """Minimal contract every connector implements."""

    name: str
    capability: str
    is_write: bool

    def health(self) -> HealthReport: ...
    def run(self, request: dict) -> Envelope: ...


@dataclass
class HealthReport:
    connector: str
    status: str            # ok | degraded | missing | broken
    detail: str = ""
    latency_ms: float | None = None

    @property
    def usable(self) -> bool:
        return self.status in {"ok", "degraded"}


@dataclass
class ConnectorManifest:
    name: str
    capability: str
    license: str
    requires_credentials: bool = False
    requires_network: bool = True
    is_write: bool = False
    cost: str = "free"        # free | metered | paid
    origin: str = "public_web"
    preference: int = 100     # lower = preferred
    factory: Callable[[], Connector] | None = None


@dataclass
class Registry:
    manifests: list[ConnectorManifest] = field(default_factory=list)

    def register(self, manifest: ConnectorManifest) -> None:
        self.manifests.append(manifest)

    def for_capability(self, capability: str) -> list[ConnectorManifest]:
        matches = [m for m in self.manifests if m.capability == capability]
        return sorted(matches, key=lambda m: m.preference)

    def capabilities(self) -> list[str]:
        return sorted({m.capability for m in self.manifests})

    def get(self, name: str) -> ConnectorManifest | None:
        return next((m for m in self.manifests if m.name == name), None)
