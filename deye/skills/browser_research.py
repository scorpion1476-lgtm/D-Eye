"""D-Eye Browser Research Skill.

Isolated-local browser adapter (opt-in `[browser]` extras).
Read actions (render, screenshot, accessibility snapshot) run without
extra consent. Write actions (click, fill, login, submit) require
`ConsentPolicy.allow_write=True` AND the specific action name in
`granted_actions`. Cookies never leave the device.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from deye import browser
from deye.core.policy import ConsentPolicy


def run(*, action: str,
        url: str = "",
        selector: str = "",
        fields: dict | None = None,
        out_path: str | None = None,
        profile: str | None = None,
        consent: ConsentPolicy | None = None) -> dict:
    """Actions:
        - "status"      : is Playwright available? which reason if not?
        - "render_html" : fetch page after JS render.
        - "screenshot"  : write PNG to `out_path`.
        - "a11y"        : return accessibility tree snapshot.
        - "click"       : consent-gated navigate + click(selector).
        - "fill_form"   : consent-gated navigate + fill(fields dict).
    """
    if action == "status":
        return {"action": action,
                "available": browser.is_available(),
                "reason": browser.unavailable_reason()}
    consent = consent or ConsentPolicy()
    with browser.BrowserAdapter(consent=consent, profile_name=profile) as ad:
        if action == "render_html":
            return {"action": action, "result": ad.render_html(url).to_dict()}
        if action == "screenshot":
            if not out_path:
                return {"action": action, "ok": False,
                        "reason": "out_path required"}
            return {"action": action,
                    "result": ad.screenshot(url, Path(out_path)).to_dict()}
        if action == "a11y":
            r = ad.a11y_snapshot(url)
            # Snapshot payloads may be large; return metadata only.
            return {"action": action, "ok": r.ok, "url": r.url,
                    "reason": r.reason, "has_payload": bool(r.payload)}
        if action == "click":
            return {"action": action,
                    "result": ad.navigate_and_click(url, selector).to_dict()}
        if action == "fill_form":
            return {"action": action,
                    "result": ad.fill_form(url, fields or {}).to_dict()}
    raise ValueError(f"unknown browser action: {action}")


from deye.skills import Skill  # noqa: E402

SKILL = Skill(
    name="browser_research",
    version="1.0.0",
    description=("Isolated local browser adapter with per-session context, "
                 "cookie-stays-local boundary, and consent-gated write actions. "
                 "Optional [browser] extras (Playwright, Apache-2.0)."),
    run=run,
    requires_consent=True,   # write actions require ConsentPolicy grant
    tags=("browser", "playwright", "consent-gated"),
)
