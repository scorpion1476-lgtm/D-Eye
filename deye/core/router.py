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
    meter: object | None = None      # optional UsageMeter; off by default
    _breakers: dict[str, _Breaker] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)

    def _breaker(self, name: str) -> _Breaker:
        return self._breakers.setdefault(name, _Breaker())

    def _meter(self, manifest, *, ok: bool, env: Envelope | None) -> None:
        if self.meter is None:
            return
        nbytes = len((env.content or "")) if env is not None else 0
        self.meter.record(manifest.name, capability=manifest.capability,
                          cost_class=manifest.cost, ok=ok, nbytes=nbytes,
                          ts=time.time())

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
                self._meter(manifest, ok=True, env=env)
                self.audit.append({
                    "connector": manifest.name,
                    "capability": capability,
                    "ok": True,
                    "latency_ms": round((time.monotonic() - started) * 1000, 1),
                })
                return env
            except Exception as exc:  # noqa: BLE001 -- deliberate: try next backend
                self._breaker(manifest.name).record(False)
                self._meter(manifest, ok=False, env=None)
                # Redact before truncating so a credential in the error (e.g. a
                # tokenized URL) can't leak into the audit trail.
                self.audit.append({"connector": manifest.name, "ok": False,
                                   "error": redact(str(exc))[:200]})
                last_error = f"{manifest.name}: {exc}"
                continue

        raise RouterError(f"all backends failed for '{capability}': {last_error}")

    def route_named(self, name: str, request: dict) -> Envelope:
        """Run one specific connector by name, inheriting the same consent
        gate, health check, circuit breaker, and redacted audit as `route`.

        Used by multi-source fan-out, where routing by capability alone would
        collapse every source onto the single top-preference connector.
        """
        manifest = next((m for m in self.registry.manifests if m.name == name), None)
        if manifest is None:
            raise RouterError(f"no connector named '{name}'")
        decision = self.consent.permits(manifest.name, is_write=manifest.is_write)
        if not decision.allowed:
            self.audit.append({"connector": name, "skipped": decision.reason})
            raise RouterError(decision.reason)
        if manifest.factory is None:
            raise RouterError(f"connector '{name}' has no factory")
        if self._breaker(name).is_open():
            raise RouterError(f"connector '{name}' circuit open")
        connector = manifest.factory()
        report = connector.health()
        if not report.usable:
            self._breaker(name).record(False)
            raise RouterError(f"{name}: {report.detail or report.status}")
        try:
            env = connector.run(request)
            self._breaker(name).record(True)
            self._meter(manifest, ok=True, env=env)
            self.audit.append({"connector": name, "capability": manifest.capability, "ok": True})
            return env
        except Exception as exc:  # noqa: BLE001 -- record redacted + re-raise
            self._breaker(name).record(False)
            self._meter(manifest, ok=False, env=None)
            self.audit.append({"connector": name, "ok": False,
                               "error": redact(str(exc))[:200]})
            raise

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
