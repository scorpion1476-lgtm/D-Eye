"""Branding asset validation.

Locks the four D-Eye brand SVGs + their two lossless PNG derivatives to
the manifest, and enforces the theme-usage contract:

- every asset exists at the recorded path;
- every hash matches the manifest exactly (no silent recolor/redraw);
- every SVG parses as XML;
- dark-theme assets are used ONLY where the manifest declares
  dark-mode usage; light-theme assets ONLY on light-mode usage;
- README uses the correct assets via <picture> with prefers-color-scheme;
- plugin + marketplace manifests point at the correct theme;
- derivatives are byte-identical to a base64-decode of the embedded
  raster in the corresponding SVG (no re-encode drift).
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "assets" / "branding" / "MANIFEST.json"
README = REPO_ROOT / "README.md"
PLUGIN_JSON = REPO_ROOT / "plugin" / "d-eye" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / "plugin" / "d-eye" / "marketplace.json"


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text())


@pytest.fixture(scope="module")
def manifest() -> dict:
    return _load_manifest()


# ---------------------------------------------------------------------------
# 1. Existence + integrity
# ---------------------------------------------------------------------------

def test_manifest_exists_and_parses():
    assert MANIFEST.exists(), f"manifest missing at {MANIFEST}"
    data = json.loads(MANIFEST.read_text())
    assert data["schema"] == "d-eye-branding-manifest/1"
    assert len(data["assets"]) == 4, "expected exactly 4 SVG assets"
    assert len(data["derivatives"]) == 2, "expected exactly 2 PNG derivatives"


def test_all_svgs_exist_and_sha256_matches(manifest):
    for asset in manifest["assets"]:
        path = REPO_ROOT / asset["path_in_repo"]
        assert path.exists(), f"missing asset: {path}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == asset["sha256"], (
            f"SHA-256 drift for {asset['filename']}: "
            f"expected {asset['sha256']}, got {actual}. "
            "The asset was modified — do NOT silently recolor / rasterize / "
            "redraw / crop / resize brand assets."
        )
        assert path.stat().st_size == asset["size_bytes"], (
            f"byte-count drift for {asset['filename']}"
        )


def test_all_derivatives_exist_and_sha256_matches(manifest):
    for derivative in manifest["derivatives"]:
        path = REPO_ROOT / derivative["path_in_repo"]
        assert path.exists(), f"missing derivative: {path}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == derivative["sha256"], (
            f"SHA-256 drift for {derivative['filename']}"
        )


# ---------------------------------------------------------------------------
# 2. XML/SVG parse contract
# ---------------------------------------------------------------------------

def test_every_svg_parses_as_xml(manifest):
    for asset in manifest["assets"]:
        path = REPO_ROOT / asset["path_in_repo"]
        try:
            root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
        except ET.ParseError as exc:
            pytest.fail(f"{asset['filename']} does not parse as XML: {exc}")
        assert root.tag.endswith("svg"), (
            f"{asset['filename']} root element is not <svg>: {root.tag}"
        )


def test_every_svg_declares_dimensions(manifest):
    for asset in manifest["assets"]:
        path = REPO_ROOT / asset["path_in_repo"]
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
        w = root.attrib.get("width")
        h = root.attrib.get("height")
        # every asset in the manifest declared both
        assert asset["svg_width"] == w
        assert asset["svg_height"] == h


# ---------------------------------------------------------------------------
# 3. Embedded raster fact-check
# ---------------------------------------------------------------------------

def test_embedded_raster_flag_matches_reality(manifest):
    """A file must be flagged embedded_raster.present=True iff its bytes
    actually contain a base64 data URI. No fibs, either direction."""
    b64_re = re.compile(r"data:image/(?:png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=]+")
    for asset in manifest["assets"]:
        path = REPO_ROOT / asset["path_in_repo"]
        text = path.read_text(encoding="utf-8", errors="replace")
        actually_has = bool(b64_re.search(text))
        declared_has = asset["embedded_raster"]["present"]
        assert actually_has == declared_has, (
            f"{asset['filename']}: manifest says embedded_raster={declared_has}, "
            f"but bytes say {actually_has}"
        )


def test_derivatives_are_byte_identical_to_embedded_raster(manifest):
    """The PNG derivatives are described as 'base64-decode only'.
    Assert that the byte stream you get by base64-decoding the SVG's
    embedded PNG matches the derivative bit-for-bit."""
    b64_re = re.compile(r"data:image/png;base64,([A-Za-z0-9+/=]+)")
    for derivative in manifest["derivatives"]:
        source_asset = next(
            a for a in manifest["assets"]
            if a["id"] == derivative["source_asset_id"]
        )
        svg_path = REPO_ROOT / source_asset["path_in_repo"]
        png_path = REPO_ROOT / derivative["path_in_repo"]
        payload = b64_re.search(
            svg_path.read_text(encoding="utf-8", errors="replace")
        )
        assert payload, f"no base64 PNG in {source_asset['filename']}"
        decoded = base64.b64decode(payload.group(1))
        actual = png_path.read_bytes()
        assert decoded == actual, (
            f"{derivative['filename']} is NOT byte-identical to the SVG's "
            "embedded PNG — 'lossless derivative' claim is false; someone "
            "re-encoded / re-rendered."
        )
        # Also assert the recorded png sha matches
        assert hashlib.sha256(actual).hexdigest() == derivative["sha256"]


# ---------------------------------------------------------------------------
# 4. README theme-usage contract via <picture>
# ---------------------------------------------------------------------------

def test_readme_uses_picture_element_with_theme_media_queries():
    text = README.read_text()
    assert "<picture>" in text
    assert "</picture>" in text
    assert 'media="(prefers-color-scheme: dark)"' in text
    assert 'media="(prefers-color-scheme: light)"' in text


def test_readme_dark_source_points_at_dark_asset(manifest):
    """The srcset attached to the (prefers-color-scheme: dark) source must
    resolve to a manifest asset whose theme is 'dark'."""
    text = README.read_text()
    m = re.search(
        r'<source[^>]+media="\(prefers-color-scheme: dark\)"[^>]+srcset="([^"]+)"',
        text,
    )
    assert m, "no dark-mode source in README"
    ref = m.group(1)
    asset = next((a for a in manifest["assets"]
                  if a["path_in_repo"] == ref), None)
    assert asset is not None, f"dark srcset {ref!r} not in manifest"
    assert asset["theme"] == "dark", (
        f"README dark-mode srcset points at {ref!r} which is theme={asset['theme']!r}"
    )


def test_readme_light_source_points_at_light_asset(manifest):
    text = README.read_text()
    m = re.search(
        r'<source[^>]+media="\(prefers-color-scheme: light\)"[^>]+srcset="([^"]+)"',
        text,
    )
    assert m, "no light-mode source in README"
    ref = m.group(1)
    asset = next((a for a in manifest["assets"]
                  if a["path_in_repo"] == ref), None)
    assert asset is not None, f"light srcset {ref!r} not in manifest"
    assert asset["theme"] == "light", (
        f"README light-mode srcset points at {ref!r} which is theme={asset['theme']!r}"
    )


def test_readme_fallback_img_is_a_light_asset(manifest):
    """The <img> inside <picture> is what non-<picture>-aware renderers
    show. It must be a light asset because GitHub's default markdown
    card background is light. The fallback may be either an SVG asset
    (theme=light) or a PNG derivative whose source_asset is theme=light
    (PNG derivatives render at the requested width more reliably than
    SVGs whose intrinsic width attribute may override the outer width)."""
    text = README.read_text()
    m = re.search(r'<img[^>]+src="([^"]+)"', text)
    assert m, "no <img> fallback in README"
    ref = m.group(1)
    # Try direct asset match first
    asset = next((a for a in manifest["assets"]
                  if a["path_in_repo"] == ref), None)
    if asset is not None:
        assert asset["theme"] == "light", (
            f"fallback src {ref!r} is a {asset['theme']!r} asset; "
            "must be light because GitHub's default markdown card is light"
        )
        return
    # Otherwise it must be a derivative of a theme=light asset
    derivative = next((d for d in manifest.get("derivatives", [])
                       if d["path_in_repo"] == ref), None)
    assert derivative is not None, (
        f"fallback src {ref!r} is neither a manifest asset nor a "
        "manifest derivative"
    )
    source_id = derivative["source_asset_id"]
    source = next(a for a in manifest["assets"] if a["id"] == source_id)
    assert source["theme"] == "light", (
        f"fallback derivative {ref!r} was derived from a {source['theme']!r} "
        "asset; must be derived from a light asset"
    )


# ---------------------------------------------------------------------------
# 5. Plugin + marketplace theme references match manifest
# ---------------------------------------------------------------------------

def test_plugin_json_branding_references_are_correct_themes(manifest):
    p = json.loads(PLUGIN_JSON.read_text())
    branding = p.get("branding") or {}
    light_ref = branding.get("logo_light_ref")
    dark_ref = branding.get("logo_dark_ref")
    assert light_ref and dark_ref
    light = next(a for a in manifest["assets"] if a["path_in_repo"] == light_ref)
    dark = next(a for a in manifest["assets"] if a["path_in_repo"] == dark_ref)
    assert light["theme"] == "light"
    assert dark["theme"] == "dark"


def test_marketplace_json_branding_references_are_correct_themes(manifest):
    p = json.loads(MARKETPLACE_JSON.read_text())
    branding = p.get("branding") or {}
    logo = branding.get("logo_reference")
    dark = branding.get("logo_dark_reference")
    raster = branding.get("raster_reference")
    assert logo and dark and raster
    assert next(a for a in manifest["assets"] if a["path_in_repo"] == logo)["theme"] == "light"
    assert next(a for a in manifest["assets"] if a["path_in_repo"] == dark)["theme"] == "dark"
    assert next(d for d in manifest["derivatives"] if d["path_in_repo"] == raster)["source_asset_id"].endswith("light.raster")


# ---------------------------------------------------------------------------
# 6. Anti-drift: no HTML/CSS silently recolours the asset
# ---------------------------------------------------------------------------

def test_readme_does_not_recolour_the_svg():
    text = README.read_text()
    # Any inline filter that would recolor the logo is banned.
    banned = [
        "filter=\"invert",
        "filter: invert",
        "style=\"filter",
        "hue-rotate",
    ]
    for pat in banned:
        assert pat not in text, (
            f"README contains {pat!r} — this recolours the brand asset. "
            "Pick the correct theme file instead."
        )


# ---------------------------------------------------------------------------
# 7. Sanity: GitHub social preview size limit
# ---------------------------------------------------------------------------

def test_light_derivative_fits_github_social_preview(manifest):
    """GitHub social preview: PNG/JPG/GIF under 1 MB. Our extracted PNG must qualify."""
    d = next(d for d in manifest["derivatives"] if d["id"] == "d-eye.light.png")
    path = REPO_ROOT / d["path_in_repo"]
    size = path.stat().st_size
    assert size < 1_000_000, f"light PNG is {size} bytes (>= 1 MB); cannot upload as social preview"
    assert d["mime"] == "image/png"
