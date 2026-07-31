"""Category-12 mirror-row acceptance tests.

Each Category 12 "Currently represented" row has its own acceptance
sentence -- it is not lifted merely because the feature it mirrors is
already PRODUCTION READY. Each test below asserts the specific
representation the row's acceptance describes: the module or file
exists on disk, the connector is registered with the router where
relevant, and the shape matches the catalogue text.

These are structural / in-process assertions, not live end-to-end
runs. That is honest: the mirror rows are catalogue-level statements
about what is represented in the repository, not claims that the
mirrored surface has been exercised live end-to-end. The rows that
require live external surfaces (Claude Desktop, hosted MCP,
Playwright browser, live sigstore) are deliberately NOT covered
here and stay honestly labelled elsewhere.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_ok(mod: str) -> bool:
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False


def _registered_names() -> set[str]:
    from deye.app import build_router
    from deye.core.config import Config
    r = build_router(Config.load())
    return {m.name for m in r.registry.manifests}


# ---------------------------------------------------------------------------
# C12-F001 CLI represented
# ---------------------------------------------------------------------------


def test_c12_f001_cli_module_declares_the_documented_subcommands():
    src = (REPO / "deye" / "cli.py").read_text()
    for cmd in ("status", "setup", "capabilities", "connectors", "doctor",
                "search", "fetch", "research", "evidence", "graph",
                "serve-http", "init-claude", "lifecycle"):
        assert cmd in src, f"cli.py missing subcommand token {cmd!r}"


def test_c12_f001_cli_module_is_importable_and_has_main_entry():
    from deye import cli
    assert hasattr(cli, "main") or hasattr(cli, "cmd_status")


# ---------------------------------------------------------------------------
# C12-F003 Remote streamable HTTP MCP represented
# ---------------------------------------------------------------------------


def test_c12_f003_remote_streamable_http_mcp_module_and_app_builder_present():
    from deye import remote
    assert hasattr(remote, "build_app")
    assert hasattr(remote, "serve")


# ---------------------------------------------------------------------------
# C12-F005 Web search represented (DuckDuckGo keyless)
# ---------------------------------------------------------------------------


def test_c12_f005_web_search_keyless_connector_is_registered():
    names = _registered_names()
    assert "search_duckduckgo" in names, (
        f"keyless DuckDuckGo search must be registered; saw {sorted(names)}"
    )


# ---------------------------------------------------------------------------
# C12-F006 Webpage fetching represented (safe_get + policy)
# ---------------------------------------------------------------------------


def test_c12_f006_webpage_fetch_is_registered_and_safe_get_exported():
    names = _registered_names()
    assert "web_fetch" in names
    from deye.connectors.base import safe_get
    from deye.core.policy import evaluate_url
    assert callable(safe_get) and callable(evaluate_url)


# ---------------------------------------------------------------------------
# C12-F007 Extraction represented
# ---------------------------------------------------------------------------


def test_c12_f007_extraction_module_exports_html_to_text_and_title():
    from deye.extract import extract_title, html_to_text
    assert callable(html_to_text) and callable(extract_title)
    # Round-trip a tiny sample to prove the surface is wired up.
    assert "Hi" in html_to_text("<html><body><h1>Hi</h1></body></html>")


# ---------------------------------------------------------------------------
# C12-F008 RSS represented (defusedxml + DOCTYPE guard)
# ---------------------------------------------------------------------------


def test_c12_f008_rss_connector_present_and_uses_doctype_guard():
    src = (REPO / "deye" / "connectors" / "rss.py").read_text()
    # DOCTYPE prolog guard blocks XXE without depending on a third-party
    # library. Either the stdlib-plus-scanner path or defusedxml is
    # acceptable evidence of the guard.
    assert "DOCTYPE" in src, "rss.py must contain the DOCTYPE prolog guard"
    assert ("_prolog_has_doctype" in src or "defusedxml" in src), (
        "rss.py must either import defusedxml or scan the prolog for DOCTYPE"
    )


# ---------------------------------------------------------------------------
# C12-F016 Plugin represented (mirrors C08-F001 SHAPE-VERIFIED)
# ---------------------------------------------------------------------------


def test_c12_f016_plugin_directory_ships_all_documented_pieces():
    p = REPO / "plugin" / "d-eye"
    assert p.is_dir(), "plugin/d-eye/ directory must exist"
    for sub in ("plugin.json", "marketplace.json", "mcp.json",
                "hooks", "commands", "skills"):
        assert (p / sub).exists(), f"plugin missing {sub}"


# ---------------------------------------------------------------------------
# C12-F019 Docker package represented (SHAPE ONLY -- no docker run)
# ---------------------------------------------------------------------------


def test_c12_f019_dockerfile_present_and_declares_non_root_user():
    dockerfile = REPO / "docker" / "Dockerfile"
    assert dockerfile.exists()
    txt = dockerfile.read_text()
    # Shape check only -- the container is NEVER started here.
    assert "USER " in txt
    # And there is at least one USER line whose value is not root.
    users = [ln.strip().split()[1] for ln in txt.splitlines()
             if ln.strip().upper().startswith("USER ")]
    assert users and users[-1].lower() not in ("root", "0", "0:0")


# ---------------------------------------------------------------------------
# C12-F020 GitHub publication represented (repository IS a git repo)
# ---------------------------------------------------------------------------


def test_c12_f020_repo_is_a_git_repo_and_the_deye_branch_exists():
    r = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0 and r.stdout.strip() == "true"
    # And the working branch is the one this program develops on.
    r = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    assert r.stdout.strip().startswith("feature/") or \
           r.stdout.strip() in ("main", "master"), (
        f"unexpected branch: {r.stdout.strip()}"
    )


# ---------------------------------------------------------------------------
# C12-F028 YouTube and social-platform connectors represented
# ---------------------------------------------------------------------------


def test_c12_f028_youtube_and_lawful_social_connectors_registered():
    names = _registered_names()
    for expected in ("reddit_search", "youtube_fetch", "v2ex_feed",
                     "xueqiu_fetch", "xiaoyuzhou_fetch"):
        assert expected in names, f"expected connector {expected!r} in {sorted(names)}"


def test_c12_f028_blocked_platforms_registered_as_missing_stubs():
    from deye.connectors import social_stub
    for platform in ("twitter_x", "linkedin", "facebook", "instagram",
                     "bilibili", "xiaohongshu"):
        assert platform in social_stub.PLATFORM_BOUNDARIES


# ---------------------------------------------------------------------------
# C12-F029 GitHub research connector
# ---------------------------------------------------------------------------


def test_c12_f029_github_repo_connector_registered_and_keyless():
    names = _registered_names()
    assert "github_repo" in names or "github_search" in names
    # And the underlying module reads via safe_get, not a keyed client.
    src = (REPO / "deye" / "connectors" / "github_repo.py").read_text()
    assert "safe_get" in src


# ---------------------------------------------------------------------------
# C12-F030 Multi-source contradiction detection
# ---------------------------------------------------------------------------


def test_c12_f030_evidence_graph_detects_contradictions():
    from deye.core.graph import EvidenceGraph
    # Two-source contradiction. Uses the same phrasing that the existing
    # test_graph.py::test_polarity_contradiction_detected uses so the
    # polarity detector has enough shared content to compare.
    g = EvidenceGraph.from_sources([
        {"url": "https://a.example/1", "connector": "web",
         "title": "Report", "excerpt": "The airline increased its fares in March."},
        {"url": "https://b.example/2", "connector": "web",
         "title": "Rebuttal", "excerpt": "The airline did not increase its fares in March."},
    ])
    kinds = {c.kind for c in g.contradictions}
    assert "polarity" in kinds


# ---------------------------------------------------------------------------
# C12-F031 Full evidence graph
# ---------------------------------------------------------------------------


def test_c12_f031_evidence_graph_carries_claims_and_serialises_all_formats():
    from deye.core.graph import EvidenceGraph
    g = EvidenceGraph.from_sources([
        {"url": "https://a.example/1", "title": "T", "excerpt": "Boeing shipped ten jets."},
    ])
    assert g.claims, "graph must carry at least one claim"
    d = g.to_dict()
    assert "summary" in d
    assert g.to_json().startswith("{")
    assert "evidence graph" in g.to_markdown().lower()


# ---------------------------------------------------------------------------
# Registry hygiene: prove the mirror-check assumptions above are consistent.
# ---------------------------------------------------------------------------


def test_c12_mirror_registry_probe_returns_a_non_empty_set():
    assert _registered_names(), "empty connector registry breaks every mirror test"
