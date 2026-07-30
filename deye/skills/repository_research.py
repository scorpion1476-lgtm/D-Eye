"""D-Eye Repository Research Skill.

Read-only public repository lookups through the router. Uses the
`repo.inspect` capability which today is served by the built-in GitHub
connector; other public-repo connectors can register the same
capability to extend the skill without changing this file.
"""
from __future__ import annotations

from typing import Any

from deye.app import build_router
from deye.core.config import Config
from deye.core.router import RouterError


def run(*, repo: str,
        config: Config | None = None) -> dict:
    """Look up a public repository by 'owner/name' slug or full URL.

    Returns metadata + latest commits + license + primary language,
    tagged as untrusted evidence with provenance.
    """
    config = config or Config.load()
    router = build_router(config)
    try:
        env = router.route("repo.inspect", {"repo": repo})
    except RouterError as exc:
        return {"ok": False, "repo": repo, "error": str(exc)}
    return {
        "ok": True,
        "repo": repo,
        "source": {
            "url": env.source.url, "connector": env.source.connector,
            "retrieved_at": env.source.retrieved_at, "title": env.source.title,
        },
        "trust": {"origin": env.trust.origin, "untrusted": env.trust.untrusted},
        "artifact": next(
            (a for a in env.artifacts if a.get("type") == "github_repo"),
            None,
        ),
        "content_preview": (env.content or "")[:4000],
        "warnings": list(env.warnings),
    }


from deye.skills import Skill  # noqa: E402

SKILL = Skill(
    name="repository_research",
    version="1.0.0",
    description=("Read-only public repository inspection (owner/name or full "
                 "URL) with SSRF-guarded HTTP + provenance. Extendable via "
                 "any connector that implements the repo.inspect capability."),
    run=run,
    requires_consent=False,
    tags=("repository", "code", "public"),
)
