"""Build a .mcpb (Desktop Extension / MCP Bundle) archive from plugin/d-eye/.

A .mcpb bundle is a ZIP archive that carries a plugin's manifest plus
all of its files in a canonical layout. This script builds one
deterministically (fixed mtime, sorted entries, no OS-level
attributes) using only the Python standard library.

Live signing (sigstore, OIDC) is a separate step (`scripts/sign_release.sh`)
and is not attempted here; the acceptance for C08-F013 is that a valid
bundle can be built repeatably from plugin/d-eye/.

Usage:
    python3 scripts/build_mcpb.py --plugin-dir plugin/d-eye \\
        --out build/deye.mcpb --manifest build/deye.mcpb.manifest.json

The output manifest names every file included, its SHA-256, and the
top-level bundle SHA-256, so a downstream verifier can prove a bundle
came from this repository without re-reading the archive.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path

# Deterministic timestamp for zip entries. Using a fixed epoch second
# converted to a (year, mo, dd, hr, mi, se) tuple. 2020-01-01T00:00:00Z
# is a common reproducible-build anchor.
_FIXED_ZIP_DATE = (2020, 1, 1, 0, 0, 0)


def _iter_plugin_files(plugin_dir: Path) -> list[Path]:
    files: list[Path] = []
    for root, dirs, names in os.walk(plugin_dir):
        # Reproducibility: sort walk in place.
        dirs.sort()
        for name in sorted(names):
            p = Path(root) / name
            # Skip zero-byte junk and __pycache__ if present.
            if p.name.startswith(".DS_Store"):
                continue
            if "__pycache__" in p.parts:
                continue
            files.append(p)
    return files


def _sha256_of_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_bundle(plugin_dir: Path, out_path: Path,
                 manifest_out: Path | None = None) -> dict:
    """Build a deterministic .mcpb bundle. Returns a manifest dict."""
    plugin_dir = plugin_dir.resolve()
    if not plugin_dir.is_dir():
        raise SystemExit(f"plugin dir not found: {plugin_dir}")
    plugin_json = plugin_dir / "plugin.json"
    if not plugin_json.exists():
        raise SystemExit(f"plugin.json missing under {plugin_dir}")

    # Read plugin.json to record the plugin name/version in the manifest.
    plugin_meta = json.loads(plugin_json.read_text())
    plugin_name = plugin_meta.get("name") or plugin_dir.name
    plugin_version = plugin_meta.get("version") or "0.0.0"

    files = _iter_plugin_files(plugin_dir)
    entries: list[dict] = []

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Write to an in-memory buffer first so the on-disk file appears
    # atomically at the end.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w",
                         compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as zf:
        for src in files:
            rel = src.relative_to(plugin_dir)
            arcname = f"{plugin_name}/{rel.as_posix()}"
            data = src.read_bytes()
            info = zipfile.ZipInfo(arcname, date_time=_FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            # File-mode: 0644 for regular files (drop OS-specific bits).
            info.external_attr = (0o644 & 0xFFFF) << 16
            zf.writestr(info, data)
            entries.append({
                "arcname": arcname,
                "size": len(data),
                "sha256": _sha256_of_bytes(data),
            })

    bundle_bytes = buf.getvalue()
    bundle_sha = _sha256_of_bytes(bundle_bytes)
    out_path.write_bytes(bundle_bytes)

    manifest = {
        "format": "mcpb",
        "format_version": "1",
        "plugin_name": plugin_name,
        "plugin_version": plugin_version,
        "bundle_path": str(out_path),
        "bundle_size": len(bundle_bytes),
        "bundle_sha256": bundle_sha,
        "entry_count": len(entries),
        "entries": entries,
    }
    if manifest_out is not None:
        manifest_out.parent.mkdir(parents=True, exist_ok=True)
        manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plugin-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--manifest", type=Path, default=None)
    args = ap.parse_args(argv)
    m = build_bundle(args.plugin_dir, args.out, args.manifest)
    print(json.dumps({
        "plugin_name": m["plugin_name"],
        "plugin_version": m["plugin_version"],
        "bundle_path": m["bundle_path"],
        "bundle_sha256": m["bundle_sha256"],
        "entry_count": m["entry_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
