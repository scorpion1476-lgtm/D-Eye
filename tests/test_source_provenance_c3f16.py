"""End-to-end acceptance for C03-F016: Source provenance and lawful
access controls.

The acceptance requires that every connector returns an Envelope
whose provenance is well-formed (source URL, connector name,
retrieval timestamp, content hash) and that the policy layer refuses
unsafe or unlawful URLs before they reach the network. This test
exercises both together against the real modules; no network."""
from __future__ import annotations

import unittest.mock as mock

import pytest

from deye.connectors import web_fetch
from deye.connectors.base import ConnectorError
from deye.core.policy import evaluate_url
from deye.core.provenance import Envelope, content_hash


class TestSourceProvenance:
    def test_envelope_carries_content_hash_and_timestamp(self):
        html = b"<html><body>provenance body</body></html>"
        with mock.patch.object(web_fetch, "safe_get",
                               return_value=(html, "https://ex.example/p", [])):
            env: Envelope = web_fetch.WebFetchConnector().run(
                {"url": "https://ex.example/p"})
        # Envelope fields required by C03-F016
        assert env.source.url == "https://ex.example/p"
        assert env.source.connector == "web_fetch"
        assert env.source.retrieved_at is not None
        # Content-hash provenance lives on the top-level helper and on
        # every Evidence.locator; a same-content re-fetch produces the
        # same hash so downstream tools can detect changes.
        assert env.evidence, "web_fetch must record at least one Evidence"
        first_locator = env.evidence[0].locator
        assert first_locator.startswith("sha256:"), (
            f"evidence locator must be sha256-prefixed, got {first_locator!r}"
        )
        with mock.patch.object(web_fetch, "safe_get",
                               return_value=(html, "https://ex.example/p", [])):
            env2 = web_fetch.WebFetchConnector().run(
                {"url": "https://ex.example/p"})
        assert content_hash(env.content) == content_hash(env2.content)

    def test_envelope_labels_public_web_as_untrusted(self):
        html = b"<html><body>x</body></html>"
        with mock.patch.object(web_fetch, "safe_get",
                               return_value=(html, "https://ex.example/", [])):
            env = web_fetch.WebFetchConnector().run(
                {"url": "https://ex.example/"})
        assert env.trust.origin == "public_web"
        assert env.trust.untrusted is True


class TestLawfulAccessControls:
    """The policy layer refuses categories the row calls out as
    unlawful/unsafe (private IPs, cloud metadata, and non-http/https
    schemes) BEFORE any network round-trip. These are the guarantees
    the source-provenance row depends on."""

    @pytest.mark.parametrize("url,reason_kw", [
        ("http://127.0.0.1/", "non-public"),
        ("http://169.254.169.254/", "non-public"),
        ("file:///etc/passwd", "scheme"),
        ("http://user:pass@example.com/", "userinfo"),
    ])
    def test_evaluate_url_refuses_unsafe_before_network(self, url, reason_kw):
        d = evaluate_url(url)
        assert d.allowed is False
        assert reason_kw in d.reason.lower()

    def test_safe_get_reports_policy_reason_verbatim(self):
        # web_fetch delegates to safe_get; a policy refusal propagates
        # as a ConnectorError the caller can log with the exact reason.
        from deye.connectors import base
        with mock.patch.object(base, "evaluate_url",
                               return_value=type("D", (), {
                                   "allowed": False,
                                   "reason": "blocked-for-test",
                                   "resolved_ips": []})()):
            with pytest.raises(ConnectorError) as excinfo:
                base._one_hop("http://vetted.invalid/", base.Limits(), None)
        assert "blocked-for-test" in str(excinfo.value)


class TestSocialStubsRecordLawfulReasons:
    """The five BLOCKED-BY-PLATFORM social rows (C03-F004, F008, F009,
    F010, F011) share a stub-registration mechanism whose acceptance
    is that each carries a human-readable reason and registers with
    the router as 'missing'. The multi-row wire-up covers C03-F016's
    'lawful access controls' half."""

    def test_every_named_platform_has_a_reason(self):
        from deye.connectors import social_stub
        boundaries = social_stub.PLATFORM_BOUNDARIES
        for name in ("twitter_x", "linkedin", "facebook", "instagram",
                     "bilibili", "xiaohongshu"):
            assert name in boundaries, f"missing boundary for {name}"
            reason = boundaries[name]
            # PLATFORM_BOUNDARIES is dict[str, str]; every value must be
            # a non-empty human-readable reason.
            assert isinstance(reason, str) and reason.strip(), (
                f"{name} boundary has empty reason"
            )
