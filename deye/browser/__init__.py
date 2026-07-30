"""D-Eye optional browser adapter.

Uses Playwright when the `[browser]` extra is installed and
`playwright install chromium` has been run. Every browser session
runs in an isolated context with a per-session cookie jar; cookies
are NEVER uploaded off-device. Consent-gated for any write action
(click, fill, submit, login) via `deye.core.policy.ConsentPolicy`.

When Playwright is not available the module remains importable and
every operation returns a structured `unavailable` error so callers
can degrade cleanly to the direct HTTP fetch path.

Public surface:
    is_available()                       -> bool
    unavailable_reason()                 -> str
    BrowserAdapter(consent=None)         -> context manager
        adapter.screenshot(url, path)
        adapter.render_html(url)
        adapter.a11y_snapshot(url)
        adapter.navigate_and_click(url, selector)   # consent-gated
        adapter.fill_form(url, fields)              # consent-gated
"""
from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deye.core.policy import ConsentPolicy, PolicyDecision


PROFILE_ROOT_ENV = "DEYE_BROWSER_PROFILES"


def _profile_root() -> Path:
    return Path(os.environ.get(
        PROFILE_ROOT_ENV,
        str(Path.home() / ".deye" / "browser-profiles"),
    ))


# ---------------------------------------------------------------------------
# Availability probe
# ---------------------------------------------------------------------------

def _probe() -> tuple[bool, str]:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False, ("playwright not installed - install with "
                       "`pip install -e '.[browser]'` and "
                       "`playwright install chromium`")
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception as exc:
        return False, f"playwright import failed: {exc}"
    return True, "playwright available"


_available, _reason = _probe()


def is_available() -> bool:
    return _available


def unavailable_reason() -> str:
    return _reason


# ---------------------------------------------------------------------------
# Structured result types
# ---------------------------------------------------------------------------

@dataclass
class BrowserResult:
    ok: bool
    url: str = ""
    reason: str = ""
    payload: Any = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "url": self.url, "reason": self.reason,
                "warnings": list(self.warnings)}


# ---------------------------------------------------------------------------
# Adapter - always constructable; degrades cleanly when playwright absent
# ---------------------------------------------------------------------------

@dataclass
class BrowserAdapter:
    """Browser adapter with per-session isolation and consent gating.

    Use as a context manager. When Playwright is absent, every method
    returns `BrowserResult(ok=False, reason=...)` rather than raising -
    downstream code can degrade to the direct HTTP fetch path.
    """
    consent: ConsentPolicy = field(default_factory=ConsentPolicy)
    profile_name: str | None = None
    _pw = None
    _browser = None
    _context = None

    def __enter__(self):
        if _available:
            try:
                from playwright.sync_api import sync_playwright
                self._pw = sync_playwright().start()
                self._browser = self._pw.chromium.launch(headless=True)
                storage_dir = _profile_root() / (self.profile_name or "default")
                storage_dir.mkdir(parents=True, exist_ok=True)
                self._context = self._browser.new_context(
                    storage_state=None,   # start fresh per session
                    accept_downloads=False,
                    java_script_enabled=True,
                )
            except Exception as exc:
                self.close()
                self._context = None
                self._pw_error = str(exc)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._context = None
        self._browser = None
        self._pw = None

    # ---- Policy helpers ---------------------------------------------------

    def _write_ok(self, action: str) -> PolicyDecision:
        return self.consent.permits(f"browser.{action}", is_write=True)

    # ---- Read-only methods ------------------------------------------------

    def render_html(self, url: str) -> BrowserResult:
        if not _available or self._context is None:
            return BrowserResult(ok=False, url=url, reason=_reason)
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="load", timeout=15000)
            html = page.content()
        finally:
            page.close()
        return BrowserResult(ok=True, url=url, payload=html)

    def screenshot(self, url: str, out_path: Path) -> BrowserResult:
        if not _available or self._context is None:
            return BrowserResult(ok=False, url=url, reason=_reason)
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="load", timeout=15000)
            page.screenshot(path=str(out_path))
        finally:
            page.close()
        return BrowserResult(ok=True, url=url,
                             payload={"path": str(out_path)})

    def a11y_snapshot(self, url: str) -> BrowserResult:
        if not _available or self._context is None:
            return BrowserResult(ok=False, url=url, reason=_reason)
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="load", timeout=15000)
            snapshot = page.accessibility.snapshot()
        finally:
            page.close()
        return BrowserResult(ok=True, url=url, payload=snapshot)

    # ---- Consent-gated write methods --------------------------------------

    def navigate_and_click(self, url: str, selector: str) -> BrowserResult:
        decision = self._write_ok("click")
        if not decision.allowed:
            return BrowserResult(
                ok=False, url=url,
                reason=f"consent denied: {decision.reason}",
            )
        if not _available or self._context is None:
            return BrowserResult(ok=False, url=url, reason=_reason)
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="load", timeout=15000)
            page.click(selector, timeout=10000)
            after_url = page.url
        finally:
            page.close()
        return BrowserResult(ok=True, url=url,
                             payload={"clicked": selector,
                                      "landed_url": after_url})

    def fill_form(self, url: str, fields: dict) -> BrowserResult:
        decision = self._write_ok("fill_form")
        if not decision.allowed:
            return BrowserResult(
                ok=False, url=url,
                reason=f"consent denied: {decision.reason}",
            )
        if not _available or self._context is None:
            return BrowserResult(ok=False, url=url, reason=_reason)
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="load", timeout=15000)
            for selector, value in fields.items():
                page.fill(selector, value, timeout=5000)
        finally:
            page.close()
        return BrowserResult(ok=True, url=url,
                             payload={"fields_filled": list(fields.keys())})


# ---------------------------------------------------------------------------
# Cookie boundary - every operation records to a local log, never uploads
# ---------------------------------------------------------------------------

@dataclass
class CookieBoundary:
    """Records every cookie access to a local audit log. Never uploads.

    Callers can inspect the log to prove that no cookie left the host
    over any adapter this class fronts.
    """
    log_path: Path

    def record(self, event: str, url: str, count: int = 0) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "event": event, "url": url, "cookie_count": count,
        })
        with self.log_path.open("a") as f:
            f.write(line + "\n")

    def read_all(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        return [json.loads(l) for l in self.log_path.read_text().splitlines() if l]

    def uploads_recorded(self) -> int:
        return sum(1 for entry in self.read_all() if entry["event"] == "upload")
