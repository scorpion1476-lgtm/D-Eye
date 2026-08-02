"""C05-F013 usage, cost, and rate reporting for optional adapters.

Acceptance: a usage meter records each connector call; the report aggregates
per-adapter call counts, an estimated cost (free FOSS connectors are 0, paid
adapters are priced), and a call rate; the meter is wired into the router so a
real routed call is metered; and `deye usage` reports from the persisted log.
"""
from __future__ import annotations

import json

from deye.backend.usage import UsageMeter
from deye.core.provenance import Envelope, Source
from deye.core.registry import ConnectorManifest, HealthReport, Registry
from deye.core.router import Router


# -- meter + report ---------------------------------------------------------

def test_report_counts_costs_and_rate():
    m = UsageMeter()
    t = 1000.0
    m.record("ddg", capability="search", cost_class="free", ok=True, nbytes=100, ts=t)
    m.record("ddg", capability="search", cost_class="free", ok=True, nbytes=100, ts=t + 30)
    m.record("paidsearch", capability="search", cost_class="paid", ok=True, nbytes=50, ts=t + 60)
    m.record("paidsearch", capability="search", cost_class="paid", ok=False, nbytes=0, ts=t + 120)
    rep = m.report()
    by = {a["connector"]: a for a in rep["adapters"]}
    assert by["ddg"]["calls"] == 2 and by["ddg"]["est_cost"] == 0.0
    assert by["paidsearch"]["calls"] == 2 and by["paidsearch"]["ok"] == 1 and by["paidsearch"]["errors"] == 1
    assert by["paidsearch"]["est_cost"] > 0.0                       # paid adapter costs
    assert by["ddg"]["calls_per_min"] == 4.0                 # 2 calls over 0.5 min
    assert rep["paid_adapters"] == ["paidsearch"]
    assert rep["total_calls"] == 4


def test_log_persistence_roundtrip(tmp_path):
    log = tmp_path / "usage.jsonl"
    m = UsageMeter(log_path=log)
    m.record("paidsearch", capability="search", cost_class="paid", ok=True, nbytes=10, ts=5.0)
    # a fresh meter reads the same history back from disk
    again = UsageMeter.from_log(log)
    assert len(again.records) == 1
    assert again.report()["paid_adapters"] == ["paidsearch"]
    # persisted lines are valid JSON
    assert json.loads(log.read_text().splitlines()[0])["connector"] == "paidsearch"


# -- router wiring ----------------------------------------------------------

class _FreeConn:
    name = "free_conn"
    capability = "search"
    is_write = False

    def health(self):
        return HealthReport(self.name, "ok", "ok")

    def run(self, request):
        return Envelope(content="result body", source=Source(url="x", connector=self.name))


class _PaidConn(_FreeConn):
    name = "paid_conn"


def _registry():
    reg = Registry()
    reg.register(ConnectorManifest(name="free_conn", capability="search", license="MIT",
                                   cost="free", preference=10, factory=lambda: _FreeConn()))
    reg.register(ConnectorManifest(name="paid_conn", capability="search", license="proprietary",
                                   cost="paid", preference=20, factory=lambda: _PaidConn()))
    return reg


def test_router_meters_routed_calls():
    meter = UsageMeter()
    router = Router(registry=_registry(), meter=meter)
    router.route("search", {"query": "q"})               # picks the free (top pref)
    router.route_named("paid_conn", {"query": "q"})       # explicitly the paid one
    rep = meter.report()
    by = {a["connector"]: a for a in rep["adapters"]}
    assert by["free_conn"]["cost_class"] == "free" and by["free_conn"]["est_cost"] == 0.0
    assert by["paid_conn"]["cost_class"] == "paid" and by["paid_conn"]["est_cost"] > 0.0
    assert by["free_conn"]["bytes"] == len("result body")


def test_router_without_meter_is_unaffected():
    # default: no meter, no side effects, routing still works
    router = Router(registry=_registry())
    env = router.route("search", {"query": "q"})
    assert env.content == "result body"
    assert router.meter is None


# -- CLI surface ------------------------------------------------------------

def test_deye_usage_reports_from_log(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DEYE_HOME", str(tmp_path))
    (tmp_path).mkdir(parents=True, exist_ok=True)
    UsageMeter(log_path=tmp_path / "usage.jsonl").record(
        "paidsearch", capability="search", cost_class="paid", ok=True, nbytes=10, ts=1.0)
    from deye.cli import main
    rc = main(["usage"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "paid_adapters" in out and "paidsearch" in out
