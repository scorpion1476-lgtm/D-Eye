# D-Eye — Connector Guide

Connectors turn a capability request (`search`, `fetch`, `feed`,
`repo.inspect`, `extract`) into an `Envelope` with provenance +
trust + warnings.

## Contract

Every connector class:

- exposes `name`, `capability`, `is_write` class attributes;
- implements `health() -> HealthReport` (fast, no network required);
- implements `run(request: dict) -> Envelope`;
- uses `deye.connectors.base.safe_get` / `safe_post` for network
  access — never raw urllib or requests.

Every connector module exports either `manifest(config)` (single
manifest) or `manifests(config)` (list) so `deye/app.py::build_registry`
can register it.

## Provided connectors

| Name | Capability | Keyless? | Licence | Notes |
|---|---|---|---|---|
| `search_duckduckgo` | search | yes | MIT | Default keyless web search. |
| `web_fetch` | fetch | yes | MIT | SSRF-guarded fetch + extraction. |
| `rss` | feed | yes | MIT | defusedxml + DOCTYPE prolog scan. |
| `github_repo` | repo.inspect | yes (public) | MIT | Public GitHub API, no key needed. |
| `reddit_search` / `reddit_fetch` | search / fetch | yes | MIT | Public `.json` endpoints; UA-attributed. |
| `v2ex_feed` / `v2ex_fetch` | feed / fetch | yes | MIT | Public JSON API. |
| `youtube_fetch` / `youtube_channel_feed` | fetch / feed | yes | MIT | oEmbed + channel RSS; no free search. |
| `xueqiu_fetch` | fetch | yes | MIT | Public symbol page (rate-limited). |
| `xiaoyuzhou_fetch` | fetch | yes | MIT | Public episode page. |
| `search_exa` | search | requires key | proprietary adapter | Off by default; keyless fallback via `search_duckduckgo`. |

## Platform boundaries (lawful-only stubs)

For platforms with no lawful keyless read path, D-Eye ships a stub
that reports `HealthReport(status="missing")` with a truthful reason.
The row stays in the catalogue with a `BLOCKED BY EXTERNAL PLATFORM`
status; a real adapter can later be shipped as an opt-in extra.

- `twitter_x` — free API tier deprecated.
- `linkedin` — ToS forbid unauthenticated scraping.
- `facebook` / `instagram` — Meta Graph API required.
- `bilibili` — no documented keyless public search.
- `xiaohongshu` — no documented public API.

## Writing a new connector

Fastest path: use the `connector_builder` skill.

```python
from deye.skills import invoke
r = invoke("connector_builder",
           name="my_source", capability="fetch",
           description="Public JSON connector for my_source.",
           license="MIT",
           out_path="deye/connectors/my_source.py")
```

Then:

1. Customise `run()` for your target host + parser.
2. Register the manifest in `deye/app.py::build_registry`.
3. Add `tests/test_connector_my_source.py` with monkeypatched `safe_get`.
4. Add the row to this guide.
5. Run `pytest tests/test_connector_my_source.py`.

## Rules

- Every result must be `trust.untrusted=True`.
- No credential may be logged. Errors pass through `redact()`.
- Every fetch honours `deye.core.policy.Limits` (timeout, max_bytes,
  max_redirects, max_crawl_depth, max_concurrency).
- Never bypass an SSRF check.
- Never bypass the consent gate for write actions.
- Every new dependency must appear in `docs/DEPENDENCY_AND_LICENCE_POLICY.md`
  with SPDX licence + pin + replacement path.
