"""Acceptance tests for multi-source research (C03-F015).

The point of the fix: fanning out must query every DISTINCT connector, not
route by capability (which collapses onto the single top-preference source).
These tests would fail against the old capability-routing behaviour.
"""
from __future__ import annotations

from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport, Registry
from deye.core.router import Router
from deye.research.multi_source import multi_source_search


class _FakeSearch:
    capability = "search"
    is_write = False

    def __init__(self, name: str, marker: str):
        self.name = name
        self._marker = marker

    def health(self) -> HealthReport:
        return HealthReport(self.name, "ok", "fake")

    def run(self, request: dict) -> Envelope:
        q = request["query"]
        return Envelope(
            content=f"result for {q} from {self._marker}",
            source=Source(url=f"https://{self._marker}.example/{q}",
                          connector=self.name, title=self._marker),
            trust=Trust(origin="public_web", untrusted=True),
        )


def _manifest(name: str, marker: str, pref: int) -> ConnectorManifest:
    return ConnectorManifest(name=name, capability="search", license="MIT",
                             requires_credentials=False, cost="free", preference=pref,
                             factory=lambda: _FakeSearch(name, marker))


def test_multi_source_queries_every_distinct_connector():
    reg = Registry()
    reg.register(_manifest("alpha", "ALPHA", 10))
    reg.register(_manifest("beta", "BETA", 20))
    result = multi_source_search(Router(registry=reg), "cats",
                                 capabilities=("search",), max_workers=1)
    contents = " ".join(e.content for e in result.packet.envelopes)
    # Both sources are actually queried, not just the top-preference one.
    assert "ALPHA" in contents
    assert "BETA" in contents
    assert len(result.packet.envelopes) == 2
    assert result.per_source_errors == {}


def test_multi_source_captures_per_source_errors_without_failing():
    class _Boom(_FakeSearch):
        def run(self, request):
            raise RuntimeError("boom")

    reg = Registry()
    reg.register(_manifest("alpha", "ALPHA", 10))
    reg.register(_manifest("beta", "BETA", 20))
    reg.register(ConnectorManifest(name="broken", capability="search", license="MIT",
                                   requires_credentials=False, cost="free", preference=30,
                                   factory=lambda: _Boom("broken", "BROKEN")))
    result = multi_source_search(Router(registry=reg), "cats",
                                 capabilities=("search",), max_workers=1)
    assert "broken" in result.per_source_errors
    assert len(result.packet.envelopes) == 2  # the two good sources still returned


def test_multi_source_dedupes_identical_results():
    reg = Registry()
    reg.register(_manifest("a", "SAME", 10))
    reg.register(_manifest("b", "SAME", 20))
    result = multi_source_search(Router(registry=reg), "q",
                                 capabilities=("search",), max_workers=1)
    assert len(result.packet.envelopes) == 2      # both queried
    assert result.dedup_clusters                  # identical results clustered


def test_multi_search_cli_subcommand_is_registered():
    from deye.cli import build_parser
    args = build_parser().parse_args(["multi-search", "cats"])
    assert args.command == "multi-search"
    assert args.query == "cats"
