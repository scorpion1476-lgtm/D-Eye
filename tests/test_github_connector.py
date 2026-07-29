import json

import pytest

from deye.connectors import github_repo
from deye.connectors.base import ConnectorError
from deye.connectors.github_repo import GitHubRepoConnector, _parse_target


def test_parse_target_accepts_slug_and_url():
    assert _parse_target({"repo": "octocat/Hello-World"}) == "octocat/Hello-World"
    assert _parse_target({"url": "https://github.com/octocat/Hello-World"}) == "octocat/Hello-World"
    assert _parse_target({"query": "octocat/Hello-World.git"}) == "octocat/Hello-World"


def test_parse_target_rejects_bad_input():
    with pytest.raises(ConnectorError):
        _parse_target({"repo": "not-a-slug"})
    with pytest.raises(ConnectorError):
        _parse_target({"url": "https://gitlab.com/a/b"})


def test_run_builds_envelope(monkeypatch):
    meta = {"description": "hi", "stargazers_count": 42, "language": "Python",
            "license": {"spdx_id": "MIT"}, "pushed_at": "2026-01-01T00:00:00Z"}
    commits = [{"sha": "abcdef1234", "commit": {"message": "init\n\nbody",
                                                "author": {"name": "Dev"}}}]

    def fake_get(url, *, limits, allowed_domains=None):
        payload = meta if url.endswith("/octocat/Hello-World") else commits
        return json.dumps(payload).encode(), url, []

    monkeypatch.setattr(github_repo, "safe_get", fake_get)
    env = GitHubRepoConnector().run({"repo": "octocat/Hello-World"})
    assert "octocat/Hello-World" in env.content
    assert "abcdef1" in env.content and "Dev" in env.content
    art = env.artifacts[0]
    assert art["type"] == "github_repo" and art["stars"] == 42 and art["license"] == "MIT"
    assert env.trust.untrusted is True and env.source.connector == "github_repo"


def test_run_reports_not_found(monkeypatch):
    def fake_get(url, *, limits, allowed_domains=None):
        return json.dumps({"message": "Not Found"}).encode(), url, []

    monkeypatch.setattr(github_repo, "safe_get", fake_get)
    with pytest.raises(ConnectorError):
        GitHubRepoConnector().run({"repo": "ghost/missing"})
