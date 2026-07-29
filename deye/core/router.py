"""Adaptive router: pick a healthy, policy-compliant connector; fall back on failure.

Implements the selection idea from forensic 3.2 / 10.C plus a simple circuit
breaker so a repeatedly-failing backend is skipped for a cool-off window.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from deye.core.policy import ConsentPolicy
from deye.core.provenance import Envelope
from deye.core.redact import redact
from deye.core.registry import Registry


@dataclass
class _Breaker:
    failures: int = 0
    opened_at: float = 0.0
    threshold: int = 3
    cool_off: float = 30.0

    def is_open(self) -> bool:
        if self.failures < self.threshold:
            return False
        if time.monotonic() - self.opened_at > self.cool_off:
            self.failures = 0          # half-open: allow a retry
            return False
        return True

    def record(self, ok: bool) -> None:
        if ok:
            self.failures = 0
        else:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = time.monotonic()


class RouterError(RuntimeError):
    pass


@dataclass
class Router:
    registry: Registry
    consent: ConsentPolicy = field(default_factory=ConsentPolicy)
    _breakers: dict[str, _Breaker] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)

    def _breaker(self, name: str) -> _Breaker:
        return self._breakers.setdefault(name, _Breaker())

    def route(self, capability: str, request: dict) -> Envelope:
        candidates = self.registry.for_capability(capability)
        if not candidates:
            raise RouterError(f"no connector registered for capability '{capability}'")

        last_error = "unknown"
        for manifest in candidates:
            decision = self.consent.permits(manifest.name, is_write=manifest.is_write)
            if not decision.allowed:
                self.audit.append({"connector": manifest.name, "skipped": decision.reason})
                last_error = decision.reason
                continue
            if self._breaker(manifest.name).is_open():
                self.audit.append({"connector": manifest.name, "skipped": "circuit open"})
                continue
            if manifest.factory is None:
                continue

            connector = manifest.factory()
            report = connector.health()
            if not report.usable:
                self._breaker(manifest.name).record(False)
                self.audit.append({"connector": manifest.name, "health": report.status})
                last_error = f"{manifest.name}: {report.detail or report.status}"
                continue
            try:
                started = time.monotonic()
                env = connector.run(request)
                self._breaker(manifest.name).record(True)
                self.audit.append({
                    "connector": manifest.name,
                    "capability": capability,
                    "ok": True,
                    "latency_ms": round((time.monotonic() - started) * 1000, 1),
                })
                return env
            except Exception as exc:  # noqa: BLE001 -- deliberate: try next backend
                self._breaker(manifest.name).record(False)
                # Redact before truncating so a credential in the error (e.g. a
                # tokenized URL) can't leak into the audit trail.
                self.audit.append({"connector": manifest.name, "ok": False,
                                   "error": redact(str(exc))[:200]})
                last_error = f"{manifest.name}: {exc}"
                continue

        raise RouterError(f"all backends failed for '{capability}': {last_error}")

    def health_all(self) -> list[dict]:
        out = []
        for manifest in sorted(self.registry.manifests, key=lambda m: (m.capability, m.preference)):
            report = manifest.factory().health() if manifest.factory else None
            out.append({
                "connector": manifest.name,
                "capability": manifest.capability,
                "license": manifest.license,
                "status": report.status if report else "unconfigured",
                "detail": report.detail if report else "no factory",
            })
        return out
