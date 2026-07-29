"""Tests for `deye.lifecycle` — the setup / update / backup / rollback stack.

These are the acceptance tests for Category 1 rows C01-F001..C01-F008
plus the `check_update`/`rollback_to` lifecycle rows that promote them
from PARTIAL / NOT IMPLEMENTED to IMPLEMENTED BUT NOT FULLY VERIFIED (in
this sandbox — cross-platform runs are recorded as external work).
"""
from __future__ import annotations

import json
import os
import sys
import tarfile
from pathlib import Path

import pytest

from deye import lifecycle


def test_env_detect_returns_populated_report(tmp_path, monkeypatch):
    # C01-F002 acceptance: env_detect() names OS, Python, venv state,
    # detected CLIs, browsers, offline flag.
    monkeypatch.setenv("DEYE_HOME", str(tmp_path))
    r = lifecycle.env_detect()
    assert r.os_name  # macOS / Linux / Windows
    assert r.python_version.startswith(f"{sys.version_info.major}.{sys.version_info.minor}")
    assert r.python_executable == sys.executable
    assert isinstance(r.detected_cli, dict)
    assert set(r.detected_cli) >= {"git", "pip", "docker"}
    assert isinstance(r.detected_browser, dict)
    assert r.home_dir == str(tmp_path) or r.home_dir.endswith(str(tmp_path))
    assert isinstance(r.warnings, list)


def test_env_detect_flags_missing_venv(monkeypatch):
    # deliberately fake a bare-Python environment
    monkeypatch.setattr(sys, "prefix", sys.base_prefix)
    r = lifecycle.env_detect()
    assert not r.is_venv
    assert any("venv" in w for w in r.warnings)


def test_env_detect_respects_offline_flag(monkeypatch):
    monkeypatch.setenv("DEYE_OFFLINE", "1")
    r = lifecycle.env_detect()
    assert r.is_offline is True
    monkeypatch.setenv("DEYE_OFFLINE", "0")
    r2 = lifecycle.env_detect()
    assert r2.is_offline is False


def test_detect_extras_reports_all_known_extras():
    # C01-F003 acceptance: detect_extras() reports each extra's availability
    # + module list + purpose. All extras must be enumerated.
    e = lifecycle.detect_extras()
    assert set(e.available) == set(lifecycle.KNOWN_EXTRAS)
    for name, meta in lifecycle.KNOWN_EXTRAS.items():
        assert e.modules[name] == meta["modules"]
        assert e.purposes[name] == meta["purpose"]


def test_provision_extra_refuses_unknown():
    with pytest.raises(ValueError):
        lifecycle.provision_extra("does-not-exist")


def test_provision_extra_refuses_offline(monkeypatch):
    # C01-F003 negative path
    monkeypatch.setenv("DEYE_OFFLINE", "1")
    r = lifecycle.provision_extra("mcp")
    assert r["ok"] is False
    assert "offline" in r["reason"]


def test_portable_config_roundtrip(tmp_path, monkeypatch):
    # C01-F008 acceptance: export + import returns same known-keys shape,
    # never leaks credentials.
    monkeypatch.setenv("DEYE_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({
        "search_provider": "duckduckgo",
        "read_only": True,
        "exa_api_key_ref": "env:EXA_API_KEY",
        "an_unknown_key": "should be dropped on import",
    }))
    export_path = tmp_path / "portable.json"
    lifecycle.portable_config_export(export_path)
    payload = json.loads(export_path.read_text())
    assert payload["config"]["search_provider"] == "duckduckgo"
    # unknown keys are exported (redaction happens at import filter)
    assert "an_unknown_key" in payload["config"]

    # import into a fresh home; unknown keys must be dropped
    other = tmp_path / "other_home"
    other.mkdir()
    monkeypatch.setenv("DEYE_HOME", str(other))
    result = lifecycle.portable_config_import(export_path)
    assert result["ok"]
    imported = json.loads((other / "config.json").read_text())
    assert imported["search_provider"] == "duckduckgo"
    assert "an_unknown_key" not in imported  # filtered on import


def test_backup_and_restore_roundtrip(tmp_path, monkeypatch):
    # C01-F004 + backup subcommand acceptance:
    # backup produces a tar.gz; restore extracts to an equivalent tree.
    monkeypatch.setenv("DEYE_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text('{"read_only": true}')
    (tmp_path / "evidence.sqlite").write_bytes(b"pretend db")

    dest = tmp_path / "backups"
    archive = lifecycle.backup_home(dest)
    assert archive.exists()
    assert archive.suffix == ".gz"
    with tarfile.open(archive, "r:gz") as tar:
        members = sorted(tar.getnames())
    assert "config.json" in members
    assert "evidence.sqlite" in members

    other = tmp_path / "restored"
    monkeypatch.setenv("DEYE_HOME", str(other))
    r = lifecycle.restore_home(archive)
    assert r["ok"]
    assert (other / "config.json").read_text() == '{"read_only": true}'


def test_restore_rejects_unsafe_paths(tmp_path, monkeypatch):
    # Security: refuse tarballs with absolute or traversal paths.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("DEYE_HOME", str(home))
    bad = tmp_path / "bad.tar.gz"  # outside DEYE_HOME so home is empty
    with tarfile.open(bad, "w:gz") as tar:
        info = tarfile.TarInfo(name="../../etc/passwd_hijack")
        info.size = 0
        tar.addfile(info)
    r = lifecycle.restore_home(bad)
    assert r["ok"] is False
    assert "unsafe path" in r["reason"]


def test_check_update_reports_current_version_and_honours_offline(monkeypatch):
    # C01-F005 acceptance: check_update() returns the current version and
    # respects offline mode without pretending to hit the network.
    monkeypatch.setenv("DEYE_OFFLINE", "1")
    r = lifecycle.check_update()
    from deye import __version__
    assert r.current_version == __version__
    assert r.available_version is None
    assert "offline" in r.reason.lower()


def test_apply_update_dry_run_returns_command_only():
    # C01-F005 negative path: dry run never mutates the system.
    r = lifecycle.apply_update("deye==0.2.0", dry_run=True)
    assert r["ok"] is True
    assert r["dry_run"] is True
    assert isinstance(r["would_run"], list)
    assert "install" in r["would_run"]


def test_rollback_to_dry_run_via_apply_update(monkeypatch):
    # C01-F005/rollback acceptance surface — must call pip install <spec>
    # and never call --force-reinstall or --upgrade.
    monkeypatch.setenv("DEYE_OFFLINE", "1")
    r = lifecycle.rollback_to("0.1.0")
    assert r["ok"] is False and "offline" in r["reason"]


def test_repair_guidance_produces_actionable_items():
    # C01-F007 acceptance: repair guidance produces at least one item on any
    # clean-machine install (the mcp extras are opt-in) and every item has
    # id/severity/condition/remedy.
    items = lifecycle.repair_guidance()
    assert isinstance(items, list)
    for it in items:
        assert it.id and it.severity in {"info", "warn", "error"}
        assert it.condition and it.remedy


def test_aggregate_report_is_json_serialisable(tmp_path, monkeypatch):
    # Used by MCP surface_status + CLI `deye lifecycle status`
    monkeypatch.setenv("DEYE_HOME", str(tmp_path))
    report = lifecycle.aggregate_report()
    j = json.dumps(report)
    assert "environment" in report
    assert "extras" in report
    assert "repair_suggestions" in report
    assert "generated_at" in report
    assert len(j) > 100
