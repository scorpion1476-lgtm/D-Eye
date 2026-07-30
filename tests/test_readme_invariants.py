"""README invariant regression tests.

Enforces:
- the logo is embedded via a <picture> element with prefers-color-scheme
  media queries pointing at the correct light/dark theme assets;
- the fallback <img> width is <=192 px (30 % of the previous 640 px);
- the README does not name external reference products in user-facing
  prose (attribution files are exempt but the README is not one);
- the README does not claim "51 tests" or "234+" (previously stale);
- an architecture-diagram code fence is present (Mermaid or explicit
  reference to `docs/ARCHITECTURE.md`).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"


@pytest.fixture(scope="module")
def readme_text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_uses_picture_element_with_theme_media_queries(readme_text):
    assert "<picture>" in readme_text
    assert 'media="(prefers-color-scheme: dark)"' in readme_text
    assert 'media="(prefers-color-scheme: light)"' in readme_text


def test_readme_logo_width_is_at_most_thirty_percent_of_previous(readme_text):
    """Previous rendered width was 640; new max 640 * 0.30 = 192.
    Enforce <=192 on the fallback <img> width attribute (that's the
    attribute GitHub's markdown renderer honours)."""
    m = re.search(r'<img[^>]+width="(\d+)"', readme_text)
    assert m, "fallback <img width=...> missing"
    width = int(m.group(1))
    assert width <= 192, (
        f"logo <img width={width}> exceeds the 30 % cap of 192 px "
        "(previous width was 640; new max is 640 * 0.30 = 192)."
    )
    # And explicitly forbid a resurgence of the old 640
    for m2 in re.finditer(r'width="(\d+)"', readme_text):
        assert int(m2.group(1)) <= 192, (
            f"a width={m2.group(1)} exceeds the 192-px cap"
        )


def test_readme_names_no_forbidden_external_products(readme_text):
    lowered = readme_text.lower()
    for forbidden in ("agent-reach", "opencli", "firebase", "genkit"):
        assert forbidden not in lowered, (
            f"README names forbidden external product {forbidden!r}. "
            "Attribution belongs in NOTICE and THIRD_PARTY_NOTICES.md, "
            "not in the user-facing README."
        )
    # Exa is allowed only if it's clearly identified as an optional
    # third-party adapter. Simpler rule: also forbid it, since we
    # currently reference it as "optional external search adapter".
    assert "exa-style" not in lowered
    assert "exa api" not in lowered


def test_readme_does_not_claim_stale_test_counts(readme_text):
    """Stale numbers must not resurface. The current authoritative count
    is written elsewhere (docs/TEST_EVIDENCE.md, this test file),
    updated per run."""
    for stale in ("51 tests", "51 passed", "234+ passed",
                  "129 passed", "199 passed"):
        assert stale not in readme_text, (
            f"README contains stale test-count {stale!r}. "
            "Update to the authoritative current run count."
        )


def test_readme_has_architecture_diagram_reference(readme_text):
    """Either a Mermaid diagram or a link to docs/ARCHITECTURE.md."""
    assert "```mermaid" in readme_text or "docs/ARCHITECTURE.md" in readme_text


def test_readme_uses_repository_relative_asset_paths(readme_text):
    """No external image URLs; all logo srcs are repo-relative."""
    for m in re.finditer(r'src(?:set)?="([^"]+)"', readme_text):
        val = m.group(1)
        if val.startswith("data:"):
            continue
        assert not val.startswith("http"), (
            f"README embeds external image {val!r}; use a repo-relative path"
        )
        # Every remaining ref must point at an asset in the repo
        assert val.startswith("assets/") or val.startswith("./assets/")


def test_readme_asset_paths_exist_on_disk():
    """Every asset the README references must actually exist."""
    text = README.read_text(encoding="utf-8")
    for m in re.finditer(r'src(?:set)?="([^"]+)"', text):
        rel = m.group(1)
        if rel.startswith(("http", "data:")):
            continue
        p = README.parent / rel
        assert p.exists(), f"README references missing asset: {rel}"


def test_readme_has_honest_status_banner(readme_text):
    """A verified-in-this-environment banner + explicit non-claim of
    overall production readiness."""
    lowered = readme_text.lower()
    assert "verified in this environment" in lowered
    assert "not" in lowered and "100" in lowered  # "not claimed as 100..."
