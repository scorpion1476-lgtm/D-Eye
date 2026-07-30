---
name: browser_research
description: >
  Local, isolated browser research using an opt-in Playwright adapter.
  Every session runs in a fresh browser context (no cross-session
  cookie carry-over); write actions (click, fill, submit, login) require
  explicit ConsentPolicy grant BEFORE the browser is even launched.
tools: []
tags: [browser, playwright, consent-gated, local-only]
version: 1.0.0
requires_extras: [browser]
---

# D-Eye Browser Research skill

**Trigger** when the user asks to interact with a JavaScript-rendered
page, take a screenshot, or capture the accessibility tree of a page.

**How to use.** Invoke the in-process `browser_research` skill:

- `action="status"` → check whether Playwright is installed.
- `action="render_html"` → fetch a rendered page.
- `action="screenshot"` → write a PNG to `out_path`.
- `action="a11y"` → accessibility tree snapshot.
- `action="click"` or `"fill_form"` → CONSENT-GATED write action.

**Safety rules.**

- Every session uses `storage_state=None` — no cookie carry-over.
- Cookies never leave the device (CookieBoundary audit log records
  every event; `uploads_recorded()` must be 0).
- Write actions (click, fill_form) require
  `ConsentPolicy.allow_write=True` AND the specific action name in
  `granted_actions`. Refused before touching the browser.
- If the `[browser]` extras group is not installed, every operation
  returns a structured `ok=False` with an honest reason instead of
  a fake success.

**Example.**

- User: "Use a local browser connector with explicit consent to click
  the 'Accept' button on https://example.org."
- Action: build a `ConsentPolicy(allow_write=True,
  granted_actions={"browser.click"})` and call
  `browser_research(action="click", url="...", selector="button.accept",
  consent=consent)`.
- Expected: if Playwright is installed, the click executes and the new
  URL is reported; otherwise ok=False with the install hint.
