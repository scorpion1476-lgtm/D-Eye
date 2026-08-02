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


# ---------------------------------------------------------------------------
# C04-F005 Dynamic webpage handling — live acceptance.
# Proves render_html runs JavaScript and returns the JS-mutated DOM, not the
# static source. No network: a data: URL whose inline script rewrites the DOM.
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not browser.is_available(), reason="playwright not installed")
def test_live_render_html_executes_javascript_and_returns_mutated_dom():
    html = ("data:text/html,<div id='out'>static</div>"
            "<script>document.getElementById('out').textContent="
            "'dyn'+(6*7)</script>")
    with BrowserAdapter() as a:
        r = a.render_html(html)
    assert r.ok is True
    # 'dyn42' can only appear if Chromium executed the script (6*7 == 42);
    # 'static' is the pre-JS placeholder and must be gone after the mutation.
    assert "dyn42" in r.payload
    assert "static" not in r.payload


# ---------------------------------------------------------------------------
# C04-F003 Browser automation — live acceptance.
# With explicit consent granted, a real click executes under Chromium and its
# observable effect (URL fragment) is reported; a real fill lands in the DOM.
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not browser.is_available(), reason="playwright not installed")
def test_live_navigate_and_click_clicks_a_real_element_under_consent():
    consent = ConsentPolicy(allow_write=True,
                            granted_actions={"browser.click"})
    page = "data:text/html,<button id='go'>go here</button>"
    with BrowserAdapter(consent=consent) as a:
        r = a.navigate_and_click(page, "#go")
    # page.click has no except in the adapter, so a missing/non-actionable
    # element raises TimeoutError instead of returning ok=True. ok=True here
    # means real Chromium located and clicked the button after the consent
    # gate allowed the write.
    assert r.ok is True
    assert r.payload["clicked"] == "#go"
    assert r.payload["landed_url"].startswith("data:text/html")


@pytest.mark.skipif(not browser.is_available(), reason="playwright not installed")
def test_live_fill_form_fills_a_real_input():
    consent = ConsentPolicy(allow_write=True,
                            granted_actions={"browser.fill_form"})
    page = "data:text/html,<input id='email'>"
    with BrowserAdapter(consent=consent) as a:
        r = a.fill_form(page, {"#email": "user@example.com"})
    # Playwright raises if the selector is absent, so ok=True means real
    # Chromium located the <input> and filled it.
    assert r.ok is True
    assert r.payload["fields_filled"] == ["#email"]


# ---------------------------------------------------------------------------
# C04-F001 Browser-based access — live acceptance.
# Each session runs in its own isolated Chromium context: state written in one
# session (a cookie) does not bleed into a later session's fresh context.
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not browser.is_available(), reason="playwright not installed")
def test_live_isolated_context_per_session_no_cookie_bleed():
    origin = ["https://isolation.example/"]
    with BrowserAdapter(profile_name="session-a") as a:
        assert a._context is not None            # a real Chromium context
        assert a._context.cookies(origin) == []  # starts fresh
        a._context.add_cookies([{"name": "sid", "value": "secret",
                                 "url": origin[0]}])
        assert [c["name"] for c in a._context.cookies(origin)] == ["sid"]
    # A fully separate later session must not see session-a's cookie.
    with BrowserAdapter(profile_name="session-b") as b:
        assert b._context is not None
        assert b._context.cookies(origin) == []
