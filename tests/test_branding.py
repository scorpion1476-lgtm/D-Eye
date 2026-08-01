"""Branding asset validation (approved-logo contract).

D-Eye ships exactly two approved brand icons plus the architecture
diagram, copied verbatim from the approved workspace-root originals into
assets/brand/. This test locks that contract:

- the brand manifest exists and lists exactly the four approved assets;
- every asset exists at the recorded path with the recorded SHA-256 and
  byte count (no silent recolor, resize, re-encode, or redraw);
- every SVG parses as XML;
- the six superseded brand files (the old assets/branding/ set) are gone
  and do not come back;
- the README hero uses the approved raster logo and never a superseded
  asset, and never recolours the logo with a CSS filter;
- the plugin and marketplace manifests point at the approved logo;
- the hero raster is small enough to double as a GitHub social preview.
"""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = REPO_ROOT / "assets" / "brand"
MANIFEST = BRAND_DIR / "MANIFEST.json"
README = REPO_ROOT / "README.md"
PLUGIN_JSON = REPO_ROOT / "plugin" / "d-eye" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / "plugin" / "d-eye" / "marketplace.json"

APPROVED_LOGO = "assets/brand/logo.png"

# The six superseded brand files that must stay removed.
SUPERSEDED = [
    "assets/branding/D-Eye_Icon.svg",
    "assets/branding/D-Eye_Icon1.svg",
    "assets/branding/D-Eye_Icon2.svg",
    "assets/branding/D-Eye_Icon21.svg",
    "assets/branding/derivatives/D-Eye_dark.png",
    "assets/branding/derivatives/D-Eye_light.png",
]


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


# ---------------------------------------------------------------------------
# 1. Manifest shape
# ---------------------------------------------------------------------------

def test_manifest_exists_and_parses():
    assert MANIFEST.exists(), f"brand manifest missing at {MANIFEST}"
    data = json.loads(MANIFEST.read_text())
    assert data["schema"] == "d-eye-brand/2"
    assert len(data["assets"]) == 4, "expected exactly 4 approved assets"
    ids = {a["id"] for a in data["assets"]}
    assert ids == {"logo.png", "logo.svg", "architecture.png", "architecture.svg"}


# ---------------------------------------------------------------------------
# 2. Existence + byte integrity
# ---------------------------------------------------------------------------

def test_all_assets_exist_and_sha256_matches(manifest):
    for asset in manifest["assets"]:
        path = REPO_ROOT / asset["path_in_repo"]
        assert path.exists(), f"missing asset: {path}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == asset["sha256"], (
            f"SHA-256 drift for {asset['filename']}: expected "
            f"{asset['sha256']}, got {actual}. Do NOT recolor, resize, "
            "re-encode, or redraw approved brand assets."
        )
        assert path.stat().st_size == asset["size_bytes"], (
            f"byte-count drift for {asset['filename']}"
        )


def test_every_svg_parses_as_xml(manifest):
    for asset in manifest["assets"]:
        if asset["mime"] != "image/svg+xml":
            continue
        path = REPO_ROOT / asset["path_in_repo"]
        try:
            root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
        except ET.ParseError as exc:
            pytest.fail(f"{asset['filename']} does not parse as XML: {exc}")
        assert root.tag.endswith("svg"), (
            f"{asset['filename']} root element is not <svg>: {root.tag}"
        )


# ---------------------------------------------------------------------------
# 3. Superseded assets must stay removed
# ---------------------------------------------------------------------------

def test_superseded_brand_files_are_gone():
    for rel in SUPERSEDED:
        assert not (REPO_ROOT / rel).exists(), (
            f"superseded brand file resurfaced: {rel}. Only the approved "
            "assets under assets/brand/ may ship."
        )
    assert not (REPO_ROOT / "assets" / "branding").exists(), (
        "the old assets/branding/ directory must not come back"
    )


# ---------------------------------------------------------------------------
# 4. README uses the approved hero and no superseded / recoloured asset
# ---------------------------------------------------------------------------

def test_readme_hero_is_the_approved_logo():
    text = README.read_text()
    assert f'src="{APPROVED_LOGO}"' in text, (
        f"README hero must reference the approved logo {APPROVED_LOGO!r}"
    )


def test_readme_never_references_a_superseded_asset():
    text = README.read_text()
    assert "assets/branding" not in text, (
        "README references the superseded assets/branding/ path"
    )


def test_readme_does_not_recolour_the_logo():
    text = README.read_text()
    banned = ['filter="invert', "filter: invert", 'style="filter', "hue-rotate"]
    for pat in banned:
        assert pat not in text, (
            f"README contains {pat!r}, which recolours the brand asset."
        )


# ---------------------------------------------------------------------------
# 5. Plugin + marketplace manifests point at the approved logo
# ---------------------------------------------------------------------------

def test_plugin_json_branding_points_at_approved_logo():
    p = json.loads(PLUGIN_JSON.read_text())
    branding = p.get("branding") or {}
    assert branding.get("logo") == "assets/brand/logo.svg"
    assert branding.get("logo_raster") == APPROVED_LOGO
    assert branding.get("manifest_ref") == "assets/brand/MANIFEST.json"
    for v in branding.values():
        assert "assets/branding" not in v, "plugin.json still names a superseded asset"


def test_marketplace_json_branding_points_at_approved_logo():
    p = json.loads(MARKETPLACE_JSON.read_text())
    branding = p.get("branding") or {}
    assert branding.get("logo_reference") == "assets/brand/logo.svg"
    assert branding.get("raster_reference") == APPROVED_LOGO
    assert branding.get("manifest_reference") == "assets/brand/MANIFEST.json"
    for v in branding.values():
        assert "assets/branding" not in v, "marketplace.json still names a superseded asset"


# ---------------------------------------------------------------------------
# 6. Sanity: hero raster fits GitHub social preview (< 1 MB PNG)
# ---------------------------------------------------------------------------

def test_hero_logo_fits_github_social_preview(manifest):
    logo = next(a for a in manifest["assets"] if a["id"] == "logo.png")
    path = REPO_ROOT / logo["path_in_repo"]
    size = path.stat().st_size
    assert size < 1_000_000, f"logo.png is {size} bytes (>= 1 MB)"
    assert logo["mime"] == "image/png"
