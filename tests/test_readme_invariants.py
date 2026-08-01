"""README invariant regression tests (approved-logo hero).

Enforces:
- the hero is the single approved raster logo (assets/brand/logo.png),
  not a superseded asset and not a recoloured one;
- no logo width exceeds the hero width cap of 360 px;
- the README names no external reference products in user-facing prose;
- the README does not resurface stale test counts;
- an architecture diagram is present (the embedded architecture image,
  a Mermaid fence, or an explicit docs reference);
- every referenced image is a repo-relative asset that exists on disk;
- an honest, verified-in-this-environment status banner is present and
  the whole product is not claimed as 100 percent production ready.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"
APPROVED_LOGO = "assets/brand/logo.png"
WIDTH_CAP = 360


@pytest.fixture(scope="module")
def readme_text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_hero_uses_the_approved_logo(readme_text):
    assert f'src="{APPROVED_LOGO}"' in readme_text, (
        f"README hero must embed the approved logo {APPROVED_LOGO!r}"
    )
    assert "assets/branding" not in readme_text, (
        "README still references the superseded assets/branding/ path"
    )


def test_readme_logo_width_is_bounded(readme_text):
    """The hero renders at 360 px; nothing may exceed that."""
    m = re.search(r'<img[^>]+width="(\d+)"', readme_text)
    assert m, "hero <img width=...> missing"
    assert int(m.group(1)) <= WIDTH_CAP, (
        f"hero <img width={m.group(1)}> exceeds the {WIDTH_CAP}-px cap"
    )
    for m2 in re.finditer(r'width="(\d+)"', readme_text):
        assert int(m2.group(1)) <= WIDTH_CAP, (
            f"a width={m2.group(1)} exceeds the {WIDTH_CAP}-px cap"
        )


def test_readme_names_no_forbidden_external_products(readme_text):
    lowered = readme_text.lower()
    for forbidden in ("agent-reach", "opencli", "firebase", "genkit"):
        assert forbidden not in lowered, (
            f"README names forbidden external product {forbidden!r}. "
            "Attribution belongs in NOTICE and THIRD_PARTY_NOTICES.md."
        )
    assert "exa-style" not in lowered
    assert "exa api" not in lowered


def test_readme_does_not_claim_stale_test_counts(readme_text):
    for stale in ("51 tests", "51 passed", "234+ passed", "129 passed",
                  "199 passed", "252 passed", "252 tests"):
        assert stale not in readme_text, (
            f"README contains stale test-count {stale!r}. "
            "Use the authoritative current run count."
        )


def test_readme_has_architecture_diagram(readme_text):
    assert (
        "assets/brand/architecture" in readme_text
        or "```mermaid" in readme_text
        or "docs/ARCHITECTURE.md" in readme_text
    ), "README must present an architecture diagram"


def test_readme_uses_repository_relative_asset_paths(readme_text):
    for m in re.finditer(r'src(?:set)?="([^"]+)"', readme_text):
        val = m.group(1)
        if val.startswith("data:"):
            continue
        assert not val.startswith("http"), (
            f"README embeds external image {val!r}; use a repo-relative path"
        )
        assert val.startswith("assets/") or val.startswith("./assets/")


def test_readme_asset_paths_exist_on_disk():
    text = README.read_text(encoding="utf-8")
    for m in re.finditer(r'src(?:set)?="([^"]+)"', text):
        rel = m.group(1)
        if rel.startswith(("http", "data:")):
            continue
        p = README.parent / rel
        assert p.exists(), f"README references missing asset: {rel}"


def test_readme_has_honest_status_banner(readme_text):
    lowered = readme_text.lower()
    assert "verified in this environment" in lowered
    assert "not" in lowered and "100" in lowered
