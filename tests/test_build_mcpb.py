"""Tests for scripts/build_mcpb.py (C08-F013 Desktop Extension/MCPB packaging).

These tests build a real .mcpb bundle from plugin/d-eye/ into tmp_path,
open the resulting archive with the stdlib zipfile module, and verify:

- the archive is a valid ZIP,
- it contains plugin.json / marketplace.json / mcp.json under the
  plugin's namespaced root,
- the build is deterministic (rebuild is byte-identical),
- and every manifest entry's SHA-256 matches the stored bytes.

No network, no Docker, no signing. Live sigstore signing (C09-F007 /
C12-F033) stays a separate step.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO / "plugin" / "d-eye"
SCRIPT = REPO / "scripts" / "build_mcpb.py"


def _run_build(out_dir: Path) -> dict:
    out_path = out_dir / "deye.mcpb"
    manifest_path = out_dir / "deye.mcpb.manifest.json"
    r = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--plugin-dir", str(PLUGIN_DIR),
         "--out", str(out_path),
         "--manifest", str(manifest_path)],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert r.returncode == 0, (
        f"build_mcpb.py failed rc={r.returncode}\nstdout: {r.stdout}\n"
        f"stderr: {r.stderr}"
    )
    assert out_path.exists() and out_path.stat().st_size > 0
    assert manifest_path.exists()
    return {
        "out": out_path,
        "manifest": manifest_path,
        "stdout": r.stdout,
        "stderr": r.stderr,
    }


def test_build_mcpb_produces_a_readable_zip_with_the_plugin_files(tmp_path):
    result = _run_build(tmp_path)
    with zipfile.ZipFile(result["out"], "r") as zf:
        names = zf.namelist()
        # Plugin files must be namespaced under the plugin name so the
        # bundle unpacks into a single top-level directory.
        assert any(n.endswith("plugin.json") for n in names), (
            f"plugin.json missing from bundle; entries: {names[:20]}"
        )
        assert any(n.endswith("marketplace.json") for n in names)
        assert any(n.endswith("mcp.json") for n in names)
        # The single top-level dir is the plugin name.
        tops = {n.split("/", 1)[0] for n in names}
        assert tops == {"d-eye"}, f"unexpected top-level: {tops}"
        # The archive is not corrupt.
        assert zf.testzip() is None


def test_build_mcpb_is_deterministic_across_rebuilds(tmp_path):
    r1 = _run_build(tmp_path / "a")
    r2 = _run_build(tmp_path / "b")
    b1 = r1["out"].read_bytes()
    b2 = r2["out"].read_bytes()
    assert hashlib.sha256(b1).hexdigest() == hashlib.sha256(b2).hexdigest(), (
        "bundle build is not byte-reproducible"
    )


def test_build_mcpb_manifest_hashes_match_the_bundle_contents(tmp_path):
    result = _run_build(tmp_path)
    manifest = json.loads(result["manifest"].read_text())
    assert manifest["format"] == "mcpb"
    assert manifest["plugin_name"] == "d-eye"
    assert manifest["plugin_version"]
    assert manifest["bundle_size"] == result["out"].stat().st_size
    assert manifest["bundle_sha256"] == hashlib.sha256(
        result["out"].read_bytes()
    ).hexdigest()
    # Every entry's stored SHA256 must equal the SHA256 of the bytes we
    # can read back through zipfile.
    with zipfile.ZipFile(result["out"], "r") as zf:
        for entry in manifest["entries"]:
            data = zf.read(entry["arcname"])
            assert entry["size"] == len(data)
            assert entry["sha256"] == hashlib.sha256(data).hexdigest(), (
                f"hash mismatch for {entry['arcname']}"
            )


def test_build_mcpb_stdout_reports_a_summary(tmp_path):
    result = _run_build(tmp_path)
    summary = json.loads(result["stdout"])
    assert summary["plugin_name"] == "d-eye"
    assert summary["entry_count"] > 0
    assert summary["bundle_sha256"]
