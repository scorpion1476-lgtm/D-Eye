"""D-Eye skills package.

Each skill is a concrete Python callable that composes existing D-Eye
primitives (router, evidence store, quality, research, browser,
backend). Skills are:

- named + registered in :data:`REGISTRY`;
- versioned via the :attr:`Skill.version` attribute;
- typed inputs and structured outputs;
- side-effect-aware (they honour ConsentPolicy);
- shipped alongside a matching `plugin/d-eye/skills/<name>/SKILL.md`
  so an MCP-compatible plugin manager exposes each.

The skills are intentionally thin: they orchestrate the well-tested
primitives rather than reimplement them. This keeps the acceptance
tests deterministic and the security guarantees traceable to one
source (the primitives).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Skill:
    name: str
    version: str
    description: str
    run: Callable[..., dict]
    requires_consent: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "requires_consent": self.requires_consent,
            "tags": list(self.tags),
        }


# Import concrete skills so REGISTRY is populated on `import deye.skills`.
from deye.skills import (  # noqa: E402  — after Skill dataclass definition
    browser_research,
    connector_builder,
    evidence as evidence_skill,
    offline_research,
    repository_research,
    research,
    source_quality,
    web_discovery,
)


REGISTRY: dict[str, Skill] = {
    research.SKILL.name: research.SKILL,
    evidence_skill.SKILL.name: evidence_skill.SKILL,
    web_discovery.SKILL.name: web_discovery.SKILL,
    browser_research.SKILL.name: browser_research.SKILL,
    repository_research.SKILL.name: repository_research.SKILL,
    source_quality.SKILL.name: source_quality.SKILL,
    offline_research.SKILL.name: offline_research.SKILL,
    connector_builder.SKILL.name: connector_builder.SKILL,
}


def list_skills() -> list[dict]:
    """Return every registered skill as a dict (for CLI + MCP surfaces)."""
    return [s.as_dict() for s in REGISTRY.values()]


def invoke(skill_name, /, **kwargs) -> dict:
    """Look up a skill by name and invoke it with keyword args.

    The lookup key is positional-only (`/`) so callers can safely pass
    `name=...` as a skill argument (e.g. connector_builder(name=...))
    without colliding with the invoke parameter.
    """
    if skill_name not in REGISTRY:
        raise KeyError(f"unknown skill: {skill_name!r}. "
                       f"Known: {sorted(REGISTRY)}")
    return REGISTRY[skill_name].run(**kwargs)
