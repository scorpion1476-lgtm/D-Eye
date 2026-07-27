import json
from pathlib import Path
from deye.init_claude import (claude_desktop_config_path, deye_server_entry,
                              merge_config, write_desktop_config, claude_code_command)

def test_config_path_is_os_appropriate():
    p = str(claude_desktop_config_path())
    assert p.endswith("claude_desktop_config.json")

def test_merge_preserves_other_servers():
    existing = json.dumps({"mcpServers": {"other": {"command": "x"}}})
    out = merge_config(existing, deye_server_entry("python3"))
    assert "other" in out["data"]["mcpServers"]
    assert out["data"]["mcpServers"]["deye"]["args"] == ["-m", "deye.mcp_server"]
    assert out["changed"] is True

def test_merge_idempotent():
    entry = deye_server_entry("python3")
    first = merge_config(None, entry)
    second = merge_config(json.dumps(first["data"]), entry)
    assert second["changed"] is False

def test_write_dry_run_touches_nothing(tmp_path):
    target = tmp_path / "claude_desktop_config.json"
    res = write_desktop_config("python3", dry_run=True, path=target)
    assert res["dry_run"] is True and not target.exists()

def test_write_creates_and_backs_up(tmp_path):
    target = tmp_path / "claude_desktop_config.json"
    target.write_text(json.dumps({"mcpServers": {"keepme": {"command": "y"}}}))
    res = write_desktop_config("python3", path=target)
    data = json.loads(target.read_text())
    assert "keepme" in data["mcpServers"] and "deye" in data["mcpServers"]
    assert res["backup"] and Path(res["backup"]).exists()

def test_claude_code_command_shape():
    cmd = claude_code_command("python3")
    assert cmd[:5] == ["claude", "mcp", "add", "--scope", "user"] and "deye" in cmd
