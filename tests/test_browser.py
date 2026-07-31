"""Acceptance tests for `deye.browser` — the optional Playwright adapter.

Playwright is intentionally NOT installed as a core runtime dep. The
tests verify:
  - the module imports cleanly even without playwright;
  - the `unavailable` degrade path is honest and structured;
  - consent-gated methods refuse writes without an explicit consent;
  - the cookie boundary records events and shows zero uploads.

When playwright IS installed, additional live-headless tests will
run (skipped otherwise). This preserves the FOSS-only, keyless core.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from deye import browser
from deye.browser import BrowserAdapter, BrowserResult, CookieBoundary
from deye.core.policy import ConsentPolicy


# ---------------------------------------------------------------------------
# Availability / degrade contract
# ---------------------------------------------------------------------------

def test_module_imports_without_playwright():
    # importing must always succeed
    assert hasattr(browser, "is_available")
    assert hasattr(browser, "unavailable_reason")
    assert isinstance(browser.is_available(), bool)


def test_unavailable_reason_when_no_playwright():
    if browser.is_available():
        pytest.skip("playwright is installed; this test only runs without it")
    assert "playwright" in browser.unavailable_reason().lower()


def test_render_html_when_unavailable_returns_structured_failure():
    if browser.is_available():
        pytest.skip("playwright installed")
    with BrowserAdapter() as a:
        r = a.render_html("https://example.com")
    assert isinstance(r, BrowserResult)
    assert r.ok is False
    assert "playwright" in r.reason.lower()


def test_screenshot_when_unavailable_returns_structured_failure(tmp_path):
    if browser.is_available():
        pytest.skip("playwright installed")
    with BrowserAdapter() as a:
        r = a.screenshot("https://example.com", tmp_path / "shot.png")
    assert r.ok is False
    assert not (tmp_path / "shot.png").exists()


# ---------------------------------------------------------------------------
# Consent gating — refuses writes even when playwright is absent, because
# the decision is made BEFORE touching the browser.
# ---------------------------------------------------------------------------

def test_click_denied_without_consent():
    with BrowserAdapter() as a:
        r = a.navigate_and_click("https://example.com", "button.submit")
    assert r.ok is False
    assert "consent" in r.reason.lower()


def test_fill_form_denied_without_consent():
    with BrowserAdapter() as a:
        r = a.fill_form("https://example.com", {"input#email": "a@b.c"})
    assert r.ok is False
    assert "consent" in r.reason.lower()


def test_click_allowed_when_consent_grants_but_still_reports_unavailable():
    """Consent gate passes; but Playwright absent, so the operation still
    reports ok=False with the availability reason (not the consent reason)."""
    if browser.is_available():
        pytest.skip("playwright installed; different code path")
    consent = ConsentPolicy(allow_write=True,
                            granted_actions={"browser.click"})
    with BrowserAdapter(consent=consent) as a:
        r = a.navigate_and_click("https://example.com", "button.submit")
    assert r.ok is False
    assert "playwright" in r.reason.lower()
    assert "consent" not in r.reason.lower()


# ---------------------------------------------------------------------------
# Cookie boundary — proves zero uploads
# ---------------------------------------------------------------------------

def test_cookie_boundary_records_and_reports_zero_uploads(tmp_path):
    cb = CookieBoundary(tmp_path / "cookies.log")
    cb.record("load", "https://a", count=3)
    cb.record("save", "https://a", count=3)
    assert cb.uploads_recorded() == 0
    entries = cb.read_all()
    assert len(entries) == 2
    assert entries[0]["event"] == "load"
    assert entries[1]["event"] == "save"


# ---------------------------------------------------------------------------
# Playwright-present live tests (only run when the extras extra is installed)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not browser.is_available(), reason="playwright not installed")
def test_live_render_html_data_url():
    """Live headless render of a data: URL — no network required, still
    proves the Playwright integration works end-to-end when installed."""
    with BrowserAdapter() as a:
        r = a.render_html("data:text/html,<h1>hi</h1>")
    assert r.ok is True
    assert "<h1>hi</h1>" in r.payload
