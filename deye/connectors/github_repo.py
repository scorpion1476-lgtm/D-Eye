"""GitHub research connector (read-only).

Inspects a public repository through the GitHub REST API, reusing the
SSRF-guarded, connection-pinned :func:`deye.connectors.base.safe_get` path so
the request is subject to the same policy engine as every other fetch.

Read-only by construction: it only issues GET against ``api.github.com`` and
never mutates anything. No credentials are required for public data; requests
are subject to GitHub's unauthenticated rate limit, which is surfaced as a
warning rather than an exception.
"""

from __future__ import annotations

import json
import re
import urllib.parse

from deye.connectors.base import ConnectorError, safe_get, timed_health
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport

_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_API = "https://api.github.com"


def _parse_target(request: dict) -> str:
    """Return an ``owner/repo`` slug from several accepted request shapes."""
    raw = (request.get("repo") or request.get("query") or request.get("url") or "").strip()
    if not raw:
        raise ConnectorError("github connector needs 'repo' as owner/name (or a github URL)")
    if raw.startswith("http"):
        parts = urllib.parse.urlsplit(raw)
        if parts.netloc not in ("github.com", "www.github.com"):
            raise ConnectorError(f"not a github.com URL: {raw}")
        segs = [s for s in parts.path.split("/") if s]
        if len(segs) < 2:
            raise ConnectorError(f"cannot extract owner/repo from URL: {raw}")
        raw = f"{segs[0]}/{segs[1]}"
    raw = raw.removesuffix(".git")
    if not _SLUG.match(raw):
        raise ConnectorError(f"invalid repo slug: {raw!r} (expected owner/name)")
    return raw


def _get_json(url: str, config: Config) -> tuple[object, list[str]]:
    body, _final, warnings = safe_get(url, limits=config.limits)
    text = body.decode("utf-8", errors="replace")
    try:
        return json.loads(text), warnings
    except json.JSONDecodeError as exc:
        raise ConnectorError(f"github API returned non-JSON from {url}: {exc}") from exc


class GitHubRepoConnector:
    """Read-only repository intelligence: metadata + latest commits."""

    name = "github_repo"
    capability = "repo.inspect"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(
            lambda: HealthReport(self.name, "ok", "public GitHub API (keyless, rate-limited)")
        )

    def run(self, request: dict) -> Envelope:
        slug = _parse_target(request)
        warnings: list[str] = []

        meta, w = _get_json(f"{_API}/repos/{slug}", self.config)
        warnings += w
        if isinstance(meta, dict) and meta.get("message") == "Not Found":
            raise ConnectorError(f"repository not found or private: {slug}")
        if isinstance(meta, dict) and "rate limit" in str(meta.get("message", "")).lower():
            warnings.append("github rate limit reached; results may be incomplete")

        commits, w = _get_json(f"{_API}/repos/{slug}/commits?per_page=5", self.config)
        warnings += w
        commit_lines = []
        if isinstance(commits, list):
            for c in commits:
                if not isinstance(c, dict):
                    continue
                info = (c.get("commit") or {})
                msg = (info.get("message") or "").splitlines()[0]
                sha = (c.get("sha") or "")[:7]
                author = ((info.get("author") or {}).get("name")) or "?"
                commit_lines.append(f"- {sha} {msg} - {author}")

        desc = meta.get("description") if isinstance(meta, dict) else None
        stars = meta.get("stargazers_count") if isinstance(meta, dict) else None
        lang = meta.get("language") if isinstance(meta, dict) else None
        lic = ((meta.get("license") or {}).get("spdx_id")
               if isinstance(meta, dict) else None)
        pushed = meta.get("pushed_at") if isinstance(meta, dict) else None

        content = "\n".join([
            f"Repository: {slug}",
            f"Description: {desc or '(none)'}",
            (f"Primary language: {lang or 'unknown'} | Stars: {stars} | "
            f"License: {lic or 'unknown'} | Last push: {pushed or 'unknown'}"),
            "",
            "Recent commits:",
            *(commit_lines or ["(no commits returned)"]),
        ])

        env = Envelope(
            content=content,
            source=Source(url=f"https://github.com/{slug}", connector=self.name,
                          title=f"GitHub: {slug}"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({
            "type": "github_repo",
            "slug": slug,
            "stars": stars,
            "language": lang,
            "license": lic,
            "pushed_at": pushed,
            "recent_commits": commit_lines,
        })
        return env


def manifest(config: Config | None = None) -> ConnectorManifest:
    return ConnectorManifest(
        name="github_repo", capability="repo.inspect", license="MIT",
        requires_credentials=False, cost="free", preference=10, origin="public_web",
        factory=lambda: GitHubRepoConnector(config),
    )
