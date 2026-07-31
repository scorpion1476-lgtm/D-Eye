"""Offline fixture tests for the keyless DuckDuckGo web-search connector
(C03-F001). Feed a fake DDG HTML response into the parser via
monkey-patched safe_get and assert the extracted envelope shape,
including the /l/?uddg= unwrapping. No network."""
from __future__ import annotations

import unittest.mock as mock

import pytest

from deye.connectors import web_search
from deye.connectors.web_search import DuckDuckGoSearch


DDG_HTML = b"""
<html><body>
<div class="result">
  <h2 class="result__title">
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Ffirst&rut=x">
      First <b>match</b>
    </a>
  </h2>
</div>
<div class="result">
  <h2 class="result__title">
    <a class="result__a" href="https://example.net/second">
      Second entry
    </a>
  </h2>
</div>
<div class="result">
  <h2 class="result__title">
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fnews.example%2Farticle%2F42&x=1">
      News from Example
    </a>
  </h2>
</div>
</body></html>
"""


@pytest.fixture()
def fake_safe_get():
    def _fn(url, *, limits, allowed_domains=None):
        return DDG_HTML, url, []
    with mock.patch.object(web_search, "safe_get", side_effect=_fn) as m:
        yield m


def test_c03_f001_parses_titles_and_unwraps_ddg_links(fake_safe_get):
    env = DuckDuckGoSearch().run({"query": "keyless search test"})
    # Envelope carries a Source pointing at the search URL and a
    # search_results artifact with the three parsed rows.
    assert env.source.connector == "search_duckduckgo"
    assert env.trust.untrusted is True
    artifacts = [a for a in env.artifacts if a.get("type") == "search_results"]
    assert artifacts, f"no search_results artifact in {env.artifacts}"
    results = artifacts[0]["results"]
    assert len(results) == 3
    titles = [r["title"] for r in results]
    assert "First match" in titles
    assert "Second entry" in titles
    assert "News from Example" in titles
    urls = [r["url"] for r in results]
    # DDG /l/?uddg=... entries are decoded to the real target
    assert "https://example.org/first" in urls
    assert "https://news.example/article/42" in urls
    # Plain absolute URLs pass through untouched
    assert "https://example.net/second" in urls


def test_c03_f001_query_is_urlencoded_into_ddg_endpoint(fake_safe_get):
    DuckDuckGoSearch().run({"query": "hello world & friends"})
    called_url = fake_safe_get.call_args[0][0]
    assert called_url.startswith("https://html.duckduckgo.com/html/?q=")
    assert "hello%20world" in called_url or "hello+world" in called_url


def test_c03_f001_empty_html_yields_no_results_but_no_error(fake_safe_get):
    with mock.patch.object(web_search, "safe_get",
                           return_value=(b"<html><body></body></html>",
                                         "https://html.duckduckgo.com/html/",
                                         [])):
        env = DuckDuckGoSearch().run({"query": "no matches"})
    artifacts = [a for a in env.artifacts if a.get("type") == "search_results"]
    assert artifacts and artifacts[0]["results"] == []
    assert "no results parsed" in env.content


def test_c03_f001_manifest_is_keyless_and_preferred_over_paid_adapter():
    ms = web_search.manifests()
    ddg = next(m for m in ms if m.name == "search_duckduckgo")
    exa = next(m for m in ms if m.name == "search_exa")
    assert ddg.requires_credentials is False
    assert ddg.cost == "free"
    # Lower preference number wins in the registry.
    assert ddg.preference < exa.preference, (
        "keyless FOSS default must beat the optional paid adapter"
    )
