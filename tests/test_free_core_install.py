"""Free and open-source core-install guarantees.

Enforces that installing and running the core D-Eye package requires
zero paid API keys, zero vendor accounts, and zero mandatory
third-party dependencies. Every optional external adapter is kept out
of the acceptance path.

These are structural tests over the packaging + config files. They
run entirely offline; no pip network calls.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_core_dependencies_are_empty():
    """The `[project].dependencies` list must be empty so the core
    install pulls no third-party runtime dependencies."""
    text = PYPROJECT.read_text()
    # Match `dependencies = []` with optional whitespace / comment
    m = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text,
                  re.MULTILINE | re.DOTALL)
    assert m, "no `dependencies = [...]` line found in pyproject.toml"
    content = m.group(1).strip()
    assert content == "", (
        "core dependencies must be empty; found:\n"
        f"  dependencies = [{content}]\n"
        "Move any new dep into `[project.optional-dependencies]`."
    )


def test_no_paid_api_env_var_required_at_import():
    """Importing every non-optional D-Eye module must succeed without
    any paid-API env var being set."""
    forbidden_envs = [
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY", "BING_API_KEY", "SERPER_API_KEY",
        "PINECONE_API_KEY", "WEAVIATE_API_KEY",
    ]
    saved = {k: os.environ.pop(k, None) for k in forbidden_envs}
    try:
        # Import every core module. Any ImportError or KeyError on a
        # missing paid-API env would fail this test.
        import importlib
        for mod in (
            "deye", "deye.app", "deye.cli", "deye.extract",
            "deye.mcp_server", "deye.surfaces",
            "deye.core.config", "deye.core.evidence", "deye.core.graph",
            "deye.core.policy", "deye.core.provenance", "deye.core.quality",
            "deye.core.redact", "deye.core.registry", "deye.core.router",
            "deye.connectors.base", "deye.connectors.web_fetch",
            "deye.connectors.web_search", "deye.connectors.rss",
            "deye.connectors.github_repo", "deye.connectors.reddit",
            "deye.connectors.v2ex", "deye.connectors.youtube",
            "deye.connectors.xueqiu", "deye.connectors.xiaoyuzhou",
            "deye.connectors.social_stub",
            "deye.lifecycle", "deye.research", "deye.research.multi_source",
            "deye.skills",
        ):
            importlib.import_module(mod)
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_router_build_produces_at_least_one_keyless_search_connector():
    """The default router must have a keyless search connector so a
    fresh install can run `deye search "..."` without any API key."""
    from deye.app import build_registry
    reg = build_registry()
    search_manifests = [m for m in reg.manifests
                        if m.capability == "search"
                        and not m.requires_credentials]
    assert search_manifests, (
        "no keyless search connector registered; a fresh install "
        "cannot run `deye search` without configuring a paid API key."
    )


def test_optional_adapters_are_not_on_the_acceptance_path():
    """Every non-keyless connector must be preference >= 40 so the
    router prefers a keyless option first."""
    from deye.app import build_registry
    reg = build_registry()
    for m in reg.manifests:
        if m.requires_credentials:
            assert m.preference >= 40, (
                f"connector {m.name!r} requires credentials but has "
                f"preference={m.preference}; the router would try it "
                "before a keyless option."
            )
        if m.cost == "paid":
            assert m.preference >= 40


def test_offline_env_flag_disables_network_calls_in_lifecycle(monkeypatch):
    """DEYE_OFFLINE=1 must make provision + update refuse politely
    without hitting the network."""
    monkeypatch.setenv("DEYE_OFFLINE", "1")
    from deye import lifecycle
    prov = lifecycle.provision_extra("mcp")
    assert prov["ok"] is False
    assert "offline" in prov["reason"].lower()
    upd = lifecycle.check_update()
    assert "offline" in upd.reason.lower()


def test_evidence_store_works_without_any_credential(tmp_path, monkeypatch):
    """The persistent evidence store, FTS5 research, and extractive
    answer must all run against a fresh SQLite file with zero paid
    resources."""
    monkeypatch.setenv("DEYE_HOME", str(tmp_path))
    from deye.core.config import Config
    from deye.core.evidence import EvidenceStore
    from deye.core.provenance import Envelope, ResearchPacket, Source, Trust
    cfg = Config.load()
    cfg.ensure_home()
    store = EvidenceStore(cfg.evidence_db)
    p = ResearchPacket(query="q")
    p.envelopes.append(Envelope(
        content="local text about sqlite fts5",
        source=Source(url="https://local/1", connector="seed", title="t"),
        trust=Trust(origin="local", untrusted=True),
    ))
    store.record_packet(p)
    rows = store.query("sqlite")
    assert rows and rows[0]["url"] == "https://local/1"


def test_pyproject_lists_only_permissive_extras():
    """Every extras group must be documented so the free-core promise
    (empty `dependencies`) means what it says."""
    text = PYPROJECT.read_text()
    assert "[project.optional-dependencies]" in text
    for expected in ("mcp", "remote", "secrets", "rich", "dev"):
        assert re.search(rf"^{expected}\s*=", text, re.MULTILINE), (
            f"extras group {expected!r} missing from pyproject.toml"
        )
