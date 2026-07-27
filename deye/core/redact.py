"""Redaction of secrets before anything is logged, exported, or shown to a model.

No retrieved content and no config value should ever reach a log line, an
evidence packet, or the LLM context with a live credential in it. These patterns
are intentionally broad -- over-redaction is safe, under-redaction is not.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("bearer", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}")),
    ("authorization", re.compile(r"(?i)(authorization\s*[:=]\s*)([^\s\"']+)")),
    ("mcpmarket_user_token", re.compile(r"sk_user_[A-Za-z0-9]{16,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}")),
    ("github_pat", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic_assignment", re.compile(
        r"(?i)((?:api[_-]?key|token|secret|password|passwd|cookie)\s*[:=]\s*)"
        r"([A-Za-z0-9._\-/+]{8,})"
    )),
]

_PLACEHOLDER = "[REDACTED]"


def redact(text: str) -> str:
    """Return *text* with anything credential-shaped replaced by a placeholder."""
    if not text:
        return text
    out = text
    for name, pattern in _PATTERNS:
        if name in {"authorization", "generic_assignment"}:
            out = pattern.sub(lambda m: m.group(1) + _PLACEHOLDER, out)
        else:
            out = pattern.sub(_PLACEHOLDER, out)
    return out


def redact_mapping(data: dict) -> dict:
    """Redact string values in a shallow mapping (e.g. HTTP headers)."""
    return {k: (redact(v) if isinstance(v, str) else v) for k, v in data.items()}
