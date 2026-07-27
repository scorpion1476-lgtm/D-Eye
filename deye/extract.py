"""Minimal, dependency-free HTML-to-text extraction.

Deliberately conservative: strips scripts/styles, drops tags, collapses
whitespace. Good enough for the vertical slice and for evidence excerpts; a
richer adapter (trafilatura / readability) can be registered later.
"""
from __future__ import annotations

import html
import re

_SCRIPT_STYLE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_WS = re.compile(r"[ \t\f\v]+")
_NL = re.compile(r"\n{3,}")


def extract_title(raw_html: str) -> str:
    m = _TITLE.search(raw_html or "")
    return html.unescape(m.group(1)).strip() if m else ""


def html_to_text(raw_html: str) -> str:
    text = _SCRIPT_STYLE.sub(" ", raw_html or "")
    text = re.sub(r"</(p|div|h[1-6]|li|br|tr)>", "\n", text, flags=re.IGNORECASE)
    text = _TAGS.sub("", text)
    text = html.unescape(text)
    text = _WS.sub(" ", text)
    text = _NL.sub("\n\n", text)
    return text.strip()
