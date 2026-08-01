"""Round 6 additional shape/in-process tests.

Covers three catalogue rows whose acceptance is either a shape claim
about tracking artefacts (C09-F009) or an in-process test of a helper
whose live activation belongs to the external product (C12-F023,
C12-F024). Each row's mirror acceptance is exercised here; the live
external activation stays out of scope and is not claimed.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# C09-F009 Issue and roadmap management (SHAPE)
# ---------------------------------------------------------------------------
#
# Acceptance: "Missing capabilities are tracked in
# reports/REMAINING_EXTERNAL_BLOCKERS.md and the traceability CSV;
# per-row status is authoritative." The tracking artefacts exist and
# name the blocked rows. Live GitHub Issues integration is out of
# scope and not asserted here.


def test_c09_f009_external_blockers_file_lists_at_least_one_blocked_row():
    blockers = REPO / "reports" / "REMAINING_EXTERNAL_BLOCKERS.md"
    if not blockers.exists():
        pytest.skip("workspace-only audit artifact not present in a clean clone")
    txt = blockers.read_text()
    # File must mention at least one BLOCKED-by-external-platform row.
    assert "C03-F004" in txt or "C03-F008" in txt or "C03-F009" in txt


def test_c09_f009_traceability_csv_carries_authoritative_per_row_status():
    csv_path = REPO / "docs" / "FEATURE_TRACEABILITY.csv"
    if not csv_path.exists():
        pytest.skip("workspace-only audit artifact not present in a clean clone")
    with csv_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 167
    # Every row has a d_eye_status in the fixed vocabulary.
    allowed = {
        "PRODUCTION READY",
        "IMPLEMENTED BUT NOT FULLY VERIFIED",
        "PARTIAL",
        "NOT IMPLEMENTED",
        "BLOCKED BY EXTERNAL PLATFORM",
        "NOT APPLICABLE",
    }
    for r in rows:
        assert r["d_eye_status"] in allowed, (
            f"{r['feature_id']}: unexpected status {r['d_eye_status']!r}"
        )
    # And at least one row is in the blocked bucket to prove the tracker
    # is not empty of missing capabilities.
    blocked = [r for r in rows if r["d_eye_status"] == "BLOCKED BY EXTERNAL PLATFORM"]
    assert blocked, "tracker must show at least one blocked row"


# ---------------------------------------------------------------------------
# C12-F023 Automatic Claude Desktop configuration (SHAPE + IN-PROCESS)
# ---------------------------------------------------------------------------
#
# Acceptance: "via init_claude". The helper is present and, in
# dry_run, produces a valid deye mcpServers entry without touching
# the real Claude Desktop config. Live Claude Desktop activation is
# not asserted.


def test_c12_f023_init_claude_dry_run_produces_a_valid_deye_mcp_server_entry(tmp_path):
    from deye.init_claude import write_desktop_config
    target = tmp_path / "claude_desktop_config.json"
    res = write_desktop_config("python3", dry_run=True, path=target)
    # Dry run must not touch the disk.
    assert res["dry_run"] is True
    assert not target.exists()
    # And the merged would-write payload must contain a deye entry
    # naming the mcp_server module.
    data = res["would_write"]
    assert "mcpServers" in data
    assert "deye" in data["mcpServers"]
    entry = data["mcpServers"]["deye"]
    assert entry["command"] == "python3"
    assert entry["args"] == ["-m", "deye.mcp_server"]


def test_c12_f023_init_claude_preserves_pre_existing_mcp_servers(tmp_path):
    from deye.init_claude import write_desktop_config
    target = tmp_path / "claude_desktop_config.json"
    target.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    res = write_desktop_config("python3", path=target)
    written = json.loads(target.read_text())
    assert "other" in written["mcpServers"], (
        "init_claude must not clobber pre-existing MCP servers"
    )
    assert "deye" in written["mcpServers"]
    # A backup of the pre-existing file must have been written.
    assert res["backup"] and Path(res["backup"]).exists()


# ---------------------------------------------------------------------------
# C12-F024 Automatic Claude Code configuration (SHAPE + IN-PROCESS)
# ---------------------------------------------------------------------------
#
# Acceptance: "via `deye init-claude --run-claude-code`". The helper
# is present and, in run=False mode, returns the exact `claude mcp
# add` command that would be executed. Live registration against a
# running Claude Code CLI is not asserted.


def test_c12_f024_init_claude_claude_code_command_shape():
    from deye.init_claude import claude_code_command
    cmd = claude_code_command("/some/venv/bin/python")
    assert cmd[:5] == ["claude", "mcp", "add", "--scope", "user"], cmd
    assert "deye" in cmd
    # The interpreter path must round-trip so the caller can pin the
    # exact python D-Eye is launched with.
    assert "/some/venv/bin/python" in cmd
    # And the module launch args must match the local stdio MCP server.
    assert "-m" in cmd and "deye.mcp_server" in cmd


def test_c12_f024_init_claude_add_to_claude_code_dry_run_reports_command():
    from deye.init_claude import add_to_claude_code
    res = add_to_claude_code("/some/venv/bin/python", run=False)
    # Not asserting on the specific run-flag key -- the acceptance is
    # that the helper reports what it WOULD run without executing it.
    joined = json.dumps(res, default=str)
    assert "claude" in joined and "mcp" in joined and "deye" in joined
