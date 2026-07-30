# D-Eye - Browser Research Guide

D-Eye ships an **optional** browser adapter behind the `[browser]`
extras group. The core install does not include Playwright; nothing
in the core runtime depends on it.

## Install

```bash
./.venv/bin/python -m pip install -e '.[browser]'
./.venv/bin/playwright install chromium
```

Without both steps, the adapter reports itself unavailable and every
call returns a structured `ok=False` with the install hint.

## Design constraints

- **Cookies stay local.** Each session uses `storage_state=None`; no
  cookie carry-over between sessions. `CookieBoundary` (see
  `deye/browser/__init__.py`) logs every load/save event and reports
  `uploads_recorded() == 0` at all times.
- **Consent-gated writes.** Every method that could cause a side
  effect (click, form fill, login) refuses to run unless the caller
  passes a `ConsentPolicy` with `allow_write=True` AND the specific
  action name in `granted_actions`. Refusal happens BEFORE Playwright
  is even launched.
- **Isolated per-session context.** Profile directories under
  `DEYE_BROWSER_PROFILES` (default `~/.deye/browser-profiles/`) are
  owner-only (`0o700`); names allowlisted against traversal.

## Read-only surface

- `render_html(url)` - return the DOM after JS execution.
- `screenshot(url, path)` - write a PNG to `path`.
- `a11y_snapshot(url)` - Playwright accessibility snapshot.

These require Playwright but not consent.

## Write surface (consent-gated)

- `navigate_and_click(url, selector)` - needs `browser.click` in
  `granted_actions`.
- `fill_form(url, fields)` - needs `browser.fill_form` in
  `granted_actions`.

Example:

```python
from deye.browser import BrowserAdapter
from deye.core.policy import ConsentPolicy

consent = ConsentPolicy(
    allow_write=True,
    granted_actions={"browser.click"},
)
with BrowserAdapter(consent=consent) as adapter:
    result = adapter.navigate_and_click(
        "https://example.org", "button.accept")
```

## Profiles

Named on-disk profile directories:

```python
from deye.browser import profiles
profiles.create_profile("work")
profiles.list_profiles()
profiles.remove_profile("work", confirm=True)
```

Names allowlisted to `^[A-Za-z0-9_-]{1,40}$` - no traversal, no
whitespace, no oversize.

## Fallback

Every browser method returns `BrowserResult(ok=False, reason=...)` when
Playwright is unavailable. Callers can treat that as "fall back to the
direct HTTP fetch path" - no exception, no silent success.

## Tests

- `tests/test_browser.py` covers availability probe, consent gating,
  cookie boundary, and the live headless test (skipped without
  Playwright installed).
