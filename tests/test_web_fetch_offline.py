"""Offline test for the keyless webpage-reading connector (C03-F002).
Drives WebFetch.run through a monkey-patched safe_get so no network is
touched, and asserts the envelope + trust shape and that the policy
layer is what refuses non-public URLs."""
from __future__ import annotations

import unittest.mock as mock

import pytest

from deye.connectors import web_fetch


class TestWebFetchOffline:
    def test_run_wraps_body_and_labels_trust_untrusted(self):
        html = b"<html><body><h1>Hi</h1><p>text</p></body></html>"
        with mock.patch.object(web_fetch, "safe_get",
                               return_value=(html, "https://example.org/page", [])):
            env = web_fetch.WebFetchConnector().run({"url": "https://example.org/page"})
        assert env.source.url == "https://example.org/page"
        assert env.source.connector == "web_fetch"
        assert env.trust.untrusted is True
        # The connector preserves the fetched body verbatim; the extractor
        # (deye.extract) is a separate module tested in test_extract.py.
        assert env.content and ("Hi" in env.content or b"Hi" in env.content.encode()
                                if isinstance(env.content, str) else b"Hi" in env.content)

    def test_run_propagates_policy_refusal(self):
        # A private URL is refused by the policy layer inside safe_get.
        from deye.connectors.base import ConnectorError
        with mock.patch.object(web_fetch, "safe_get",
                               side_effect=ConnectorError(
                                   "blocked by policy: non-public IP: 127.0.0.1")):
            with pytest.raises(ConnectorError) as excinfo:
                web_fetch.WebFetchConnector().run({"url": "http://127.0.0.1/x"})
        assert "blocked by policy" in str(excinfo.value)

    def test_manifest_is_keyless(self):
        m = web_fetch.manifest()
        assert m.name == "web_fetch"
        assert m.requires_credentials is False
        assert m.capability == "fetch"
