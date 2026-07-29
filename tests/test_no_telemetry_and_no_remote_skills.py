"""Enforcement tests: no silent telemetry, no remote skill downloading.

Static analysis over the tracked source tree. Fails if:
- any deye/* module contains a hard-coded URL that looks like a known
  telemetry endpoint (segment or datadog or newrelic or sentry.io or
  plausible.io or google-analytics or amplitude or mixpanel);
- any plugin hook literal invokes curl/wget/nc for a remote skill.

These make Category 11 rows F014 ("no silent telemetry") and F015 ("no
remote skill downloading") first-class testable properties instead of
documentation promises.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEYE_PKG = REPO_ROOT / "deye"
PLUGIN_ROOT = REPO_ROOT / "plugin"

# Known telemetry / analytics endpoints that must never appear in source.
_TELEMETRY_HOSTS = [
    "google-analytics.com",
    "googletagmanager.com",
    "analytics.google.com",
    "segment.com",
    "api.segment.io",
    "datadoghq.com",
    "newrelic.com",
    "sentry.io",
    "amplitude.com",
    "mixpanel.com",
    "plausible.io",
    "posthog.com",
    "api.honeycomb.io",
]

# Remote skill / config downloaders — must not appear in plugin hooks/config.
_REMOTE_DOWNLOADERS = [
    r"\bcurl\s+-[Ls]?O?\s+https?://",
    r"\bwget\s+.*https?://",
    r"\bpip\s+install\s+.*http",
]


def _walk_text_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in {".pyc", ".png", ".jpg", ".gif", ".pdf",
                                ".zip", ".gz", ".tar", ".whl", ".ico"}:
            continue
        # skip cache dirs
        if any(part.startswith(".") and part not in {".github", ".claude"}
               for part in p.parts):
            continue
        try:
            yield p, p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


def test_no_telemetry_hosts_in_deye_source():
    offenders: list[tuple[str, str]] = []
    for path, text in _walk_text_files(DEYE_PKG):
        low = text.lower()
        for host in _TELEMETRY_HOSTS:
            if host in low:
                offenders.append((str(path), host))
    assert not offenders, (
        "telemetry hosts referenced in D-Eye source:\n" +
        "\n".join(f"  {p} -> {h}" for p, h in offenders)
    )


def test_no_remote_skill_download_in_plugin():
    if not PLUGIN_ROOT.exists():
        return
    offenders: list[tuple[str, str]] = []
    pattern_re = [re.compile(p) for p in _REMOTE_DOWNLOADERS]
    for path, text in _walk_text_files(PLUGIN_ROOT):
        # allow README/CHANGELOG type docs to describe remote downloads
        # in prose — but plugin.json / hooks.json / mcp.json / *.sh /
        # commands MUST be free of them.
        if path.suffix.lower() in {".md", ".txt"}:
            continue
        for pat in pattern_re:
            if pat.search(text):
                offenders.append((str(path), pat.pattern))
    assert not offenders, (
        "remote skill download pattern in plugin:\n" +
        "\n".join(f"  {p} -> {r}" for p, r in offenders)
    )


def test_plugin_declares_safety_flags_are_true():
    """The plugin's own safety flags must all be true and must be
    testable properties, not documentation prose."""
    import json
    manifest = json.loads((PLUGIN_ROOT / "d-eye" / "plugin.json").read_text())
    safety = manifest.get("safety", {})
    assert safety.get("no_silent_telemetry") is True
    assert safety.get("no_remote_skill_downloading") is True
