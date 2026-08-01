"""Acceptance tests for one-command setup (C01-F001) and repair guidance
(C01-F007). Both exercise real behaviour, not shape.
"""
from __future__ import annotations

import json
import types


def test_setup_creates_a_read_only_config_with_no_live_secret(tmp_path, monkeypatch):
    """`deye setup` writes a working config into DEYE_HOME, read-only by
    default, storing no live credential (only an optional reference)."""
    home = tmp_path / "deye"
    monkeypatch.setenv("DEYE_HOME", str(home))
    from deye.cli import main
    assert main(["setup"]) == 0
    cfg = home / "config.json"
    assert cfg.exists(), "setup must create config.json under DEYE_HOME"
    data = json.loads(cfg.read_text())
    assert data["read_only"] is True
    # No live secret is persisted: the optional adapter key is stored only as
    # a reference (env:/keychain:) resolved at use time, never a raw value.
    ref = data.get("exa_api_key_ref") or ""
    assert ref == "" or ref.startswith(("env:", "keychain:")), (
        f"config stored something that is not a secret reference: {ref!r}")
    # Idempotent: a second run does not error or clobber.
    assert main(["setup"]) == 0
    assert json.loads(cfg.read_text())["read_only"] is True


def test_repair_guidance_emits_actionable_remedies_for_known_problems(monkeypatch):
    from deye import lifecycle
    fake_env = types.SimpleNamespace(
        is_venv=False, stdlib_paths_ok=False, python_version="3.9.0",
        detected_cli={"git": None})
    fake_extras = types.SimpleNamespace(available={"mcp": False, "browser": False})
    monkeypatch.setattr(lifecycle, "env_detect", lambda *a, **k: fake_env)
    monkeypatch.setattr(lifecycle, "detect_extras", lambda *a, **k: fake_extras)
    steps = lifecycle.repair_guidance()
    by_id = {s.id: s for s in steps}
    assert "venv.missing" in by_id
    assert "python.too_old" in by_id
    assert "cli.git_missing" in by_id
    assert "extra.mcp_missing" in by_id
    for s in steps:
        d = s.to_dict()
        assert d["remedy"].strip(), "every suggestion must carry a concrete remedy"
        assert d["severity"] in ("info", "warn", "error")


def test_repair_guidance_is_empty_when_environment_is_healthy(monkeypatch):
    from deye import lifecycle
    fake_env = types.SimpleNamespace(
        is_venv=True, stdlib_paths_ok=True, python_version="3.14.0",
        detected_cli={"git": "/usr/bin/git"})
    fake_extras = types.SimpleNamespace(available={"mcp": True, "browser": True})
    monkeypatch.setattr(lifecycle, "env_detect", lambda *a, **k: fake_env)
    monkeypatch.setattr(lifecycle, "detect_extras", lambda *a, **k: fake_extras)
    assert lifecycle.repair_guidance() == []
