import json

import pytest

from deye.connectors import web_search
from deye.connectors.base import ConnectorError
from deye.connectors.web_search import ExaSearch
from deye.core.config import Config


def _cfg_with_key(key_ref: str) -> Config:
    cfg = Config()
    cfg.exa_api_key_ref = key_ref
    return cfg


def test_keyless_health_is_missing(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    exa = ExaSearch(_cfg_with_key("env:EXA_API_KEY"))
    assert exa.health().status == "missing"


def test_keyless_run_raises_so_router_can_fall_back(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    exa = ExaSearch(_cfg_with_key("env:EXA_API_KEY"))
    with pytest.raises(ConnectorError):
        exa.run({"query": "anything"})


def test_run_with_key_parses_results_and_cost(monkeypatch):
    captured = {}

    def fake_post(url, *, limits, body, headers=None, allowed_domains=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(body.decode())
        resp = {"results": [{"title": "T", "url": "https://x.example",
                             "publishedDate": "2026-01-01", "highlights": ["h"]}],
                "costDollars": {"total": 0.01}}
        return json.dumps(resp).encode(), 200, []

    monkeypatch.setattr(web_search, "safe_post", fake_post)
    exa = ExaSearch(_cfg_with_key("literal-test-key"))  # raw ref -> used as-is
    assert exa.health().status == "ok"
    env = exa.run({"query": "airline pricing", "include_domains": ["iata.org"],
                   "start_date": "2026-01-01"})
    assert captured["headers"]["x-api-key"] == "literal-test-key"
    assert captured["url"].endswith("/search")
    assert captured["body"]["includeDomains"] == ["iata.org"]
    assert env.artifacts[0]["provider"] == "exa"
    assert any("cost" in w for w in env.warnings)
    assert env.trust.authenticated is True


def test_answer_mode_uses_answer_endpoint(monkeypatch):
    def fake_post(url, *, limits, body, headers=None, allowed_domains=None):
        assert url.endswith("/answer")
        return json.dumps({"answer": "42"}).encode(), 200, []

    monkeypatch.setattr(web_search, "safe_post", fake_post)
    env = ExaSearch(_cfg_with_key("k")).run({"mode": "answer", "query": "q"})
    assert env.content == "42"
