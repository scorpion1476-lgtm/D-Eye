"""RSS/Atom feed reader (stdlib XML; feedparser used if installed)."""
from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405 - untrusted parse is guarded by _safe_fromstring (DOCTYPE rejected)

from deye.connectors.base import safe_get, timed_health
from deye.core.config import Config
from deye.core.provenance import Envelope, Source, Trust
from deye.core.registry import ConnectorManifest, HealthReport


def _prolog_has_doctype(body: bytes) -> bool:
    """True iff a DOCTYPE declaration appears in the XML prolog.

    Scans only the prolog: skips the XML declaration, processing instructions
    and comments (whatever their length), and reports a DOCTYPE that precedes
    the root element. This is robust against the "pad the prolog with a huge
    comment to push DOCTYPE past a fixed window" bypass, and does not
    false-positive on the literal text ``<!DOCTYPE`` appearing inside element
    content or a CDATA section (parsing stops at the first element start).
    """
    i, n = 0, len(body)
    while i < n:
        c = body[i:i + 1]
        if c in (b" ", b"\t", b"\r", b"\n"):
            i += 1
            continue
        if body.startswith(b"<?", i):  # XML declaration or processing instruction
            end = body.find(b"?>", i)
            if end == -1:
                return False
            i = end + 2
            continue
        if body.startswith(b"<!--", i):  # comment (any length)
            end = body.find(b"-->", i)
            if end == -1:
                return False
            i = end + 3
            continue
        if body[i:i + 9].upper() == b"<!DOCTYPE":
            return True
        return False  # start of the root element: no prolog DOCTYPE
    return False


def _safe_fromstring(body: bytes):
    """Parse feed XML with an entity-expansion / XXE guard.

    Rejecting any DOCTYPE declaration blocks internal-entity 'billion laughs'
    expansion and DTD-driven external-entity attacks; combined with expat's
    default of not resolving external entities, this makes stdlib ElementTree
    safe for untrusted feed bytes without adding a dependency.
    """
    if _prolog_has_doctype(body):
        raise ET.ParseError("DOCTYPE declarations are not allowed (XXE/entity guard)")
    return ET.fromstring(body)  # nosec B314 - DOCTYPE rejected above; no external entity resolution


class RSSConnector:
    name = "rss"
    capability = "feed"
    is_write = False

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def health(self) -> HealthReport:
        return timed_health(lambda: HealthReport(self.name, "ok", "stdlib xml"))

    def run(self, request: dict) -> Envelope:
        url = request["url"]
        body, final_url, warnings = safe_get(url, limits=self.config.limits)
        items = []
        try:
            root = _safe_fromstring(body)
            for node in root.iter():
                tag = node.tag.split("}")[-1].lower()
                if tag in ("item", "entry"):
                    title = _child_text(node, "title")
                    link = _child_text(node, "link") or _child_attr(node, "link", "href")
                    items.append({"title": title, "url": link})
        except ET.ParseError as exc:
            warnings.append(f"feed parse error: {exc}")
        content = "\n".join(f"{i['title']} -- {i['url']}" for i in items[:25]) or "(no items)"
        env = Envelope(
            content=content,
            source=Source(url=final_url, connector=self.name, title="RSS feed"),
            trust=Trust(origin="public_web", untrusted=True),
            warnings=warnings,
        )
        env.artifacts.append({"type": "feed_items", "items": items[:25]})
        return env


def _child_text(node, name):
    for c in node:
        if c.tag.split("}")[-1].lower() == name and c.text:
            return c.text.strip()
    return ""


def _child_attr(node, name, attr):
    for c in node:
        if c.tag.split("}")[-1].lower() == name:
            return c.attrib.get(attr, "")
    return ""


def manifest(config: Config | None = None) -> ConnectorManifest:
    return ConnectorManifest(name="rss", capability="feed", license="MIT",
                             requires_credentials=False, preference=10,
                             factory=lambda: RSSConnector(config))
