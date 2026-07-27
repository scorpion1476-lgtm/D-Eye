"""The typed envelope every connector returns, plus research-packet export.

This is the data-plane contract from section 9.2 of the forensic report. The
LLM sees connector output as *untrusted evidence* carrying source metadata and
citation locators -- never as instructions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(text: str) -> str:
    """Stable SHA-256 used for citation locators and source-change detection."""
    return "sha256:" + hashlib.sha256((text or "").encode("utf-8")).hexdigest()


@dataclass
class Source:
    url: str
    connector: str
    retrieved_at: str = field(default_factory=_now)
    title: str = ""


@dataclass
class Trust:
    origin: str = "public_web"      # public_web | authenticated | local | adapter
    authenticated: bool = False
    untrusted: bool = True          # retrieved content is ALWAYS untrusted


@dataclass
class Evidence:
    locator: str                    # e.g. "sha256:...#offset" or "url#selector"
    quote_hash: str
    excerpt: str = ""


@dataclass
class Envelope:
    """Uniform result returned by every acquisition connector."""

    content: str
    source: Source
    trust: Trust = field(default_factory=Trust)
    evidence: list[Evidence] = field(default_factory=list)
    policy: dict = field(default_factory=dict)
    artifacts: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_evidence(self, excerpt: str) -> Evidence:
        ev = Evidence(
            locator=f"{content_hash(self.content)}#0-{len(excerpt)}",
            quote_hash=content_hash(excerpt),
            excerpt=excerpt[:2000],
        )
        self.evidence.append(ev)
        return ev

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResearchPacket:
    """An auditable bundle: query, every source, hashes, excerpts, warnings."""

    query: str
    created_at: str = field(default_factory=_now)
    envelopes: list[Envelope] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "created_at": self.created_at,
            "source_count": len(self.envelopes),
            "sources": [e.to_dict() for e in self.envelopes],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Human-readable, fully cited Markdown export."""
        lines = [
            f"# Research packet: {self.query}",
            "",
            f"_Generated {self.created_at} by D-Eye. "
            f"{len(self.envelopes)} source(s). All content below is untrusted evidence._",
            "",
        ]
        for i, env in enumerate(self.envelopes, 1):
            s = env.source
            lines += [
                f"## [{i}] {s.title or s.url}",
                "",
                f"- Source: <{s.url}>",
                f"- Connector: `{s.connector}`",
                f"- Retrieved: {s.retrieved_at}",
                f"- Content hash: `{content_hash(env.content)}`",
                f"- Trust: origin={env.trust.origin}, "
                f"authenticated={env.trust.authenticated}, untrusted={env.trust.untrusted}",
            ]
            if env.warnings:
                lines.append(f"- Warnings: {'; '.join(env.warnings)}")
            excerpt = (env.content or "").strip()
            if excerpt:
                snippet = excerpt[:1500] + ("\n\n_[truncated]_" if len(excerpt) > 1500 else "")
                lines += ["", "> " + snippet.replace("\n", "\n> "), ""]
        return "\n".join(lines)
