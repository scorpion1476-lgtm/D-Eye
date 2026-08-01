# D-Eye README product review

Produced 2026-07-30. This document reviews an earlier README against
the product-review checklist and records the state of each item.

> **Superseded.** The README was later redesigned. The current README uses
> a single approved raster logo (`assets/brand/logo.png`) as a centred hero
> and embeds the architecture diagram as an image, not a `<picture>`
> element or a Mermaid fence. The branding asset paths named below (under
> `assets/branding/`) were removed. Read this file as a historical record
> of the pre-redesign README, not a description of the current one.

## Header

- Small D-Eye line-icon at the top-left via a `<picture>` element.
- Fallback `<img>` uses the pre-rasterised PNG derivative at
  `assets/branding/derivatives/D-Eye_light.png` with `width="180"`
  so GitHub renders at exactly the intended size regardless of the
  intrinsic SVG width. Dark-theme visitors get the SVG via the
  `prefers-color-scheme: dark` `<source>`.
- Logo width: 180 CSS px (= 28.1 % of the former 640 px baseline;
  below the required 30 % cap).
- Title: `# D-Eye`, single line, visually dominant.
- One-sentence positioning: "A FOSS-first, local-first capability
  and evidence layer for AI agents."
- Honest status banner: exact test count (252 passed, 8 skipped),
  Bandit result, live pip-audit result, 63/167 PROD-READY row count,
  explicit "not claimed as production ready overall" statement.

## Structural coverage against the checklist

| Requirement | Location |
|---|---|
| Clean logo + title | Header |
| One-sentence definition | First bold line after title |
| Executive overview for non-technical readers | "What it solves" paragraphs |
| Who the product is for | "Who it is for" list |
| Practical problem it solves | "The practical problem" |
| What happens when a user asks a normal research question | Practical workflow 1 |
| Concise feature summary | Capabilities table |
| Distinction between available / partial / blocked / planned | Validation-status section + linked traceability CSV + Current-limitations section |
| Five-minute local quick start | "Five-minute quick start" |
| No-paid-API install path | Quick start uses `pip install -e .` with zero extras |
| Offline test path | Offline mode section + `DEYE_OFFLINE=1` env var |
| Architecture explanation | "Architecture at a glance" |
| Architecture diagram | Mermaid `flowchart LR`, ASCII-only characters |
| Capability table with honest status | Capabilities table plus the honest status section in the README |
| Skills section | Skills table + link to `docs/SKILLS_GUIDE.md` |
| Connector section | Connectors section + link to `docs/CONNECTOR_GUIDE.md`, explicitly separates keyless FOSS, optional external, and platform-boundary stubs |
| Practical commands | Nine numbered workflows |
| MCP + CLI usage | "Local and remote MCP" section |
| Security model | "Security model" bullet list of invariants each backed by a test |
| Configuration | "Configuration" section with every env var |
| Troubleshooting | Troubleshooting section + link to full guide |
| Developer setup + test commands | Developer guide section + link |
| Exact validation results | Validation-status section: exact counts, Bandit result, OSV result |
| Current limitations | "Current limitations" section |
| Licence + legally-required attribution only | Licence section with pointer to `THIRD_PARTY_NOTICES.md` |
| Roadmap | Roadmap section with concrete next steps |

## Non-goals honoured

- No "enterprise-grade", "fully complete", "production-ready overall",
  or "100 percent complete" language.
- No em / en / non-breaking-hyphen characters (regression test:
  `tests/test_ui_dashes.py`).
- No external product names in user-facing prose (regression test:
  `tests/test_readme_invariants.py`; attribution lives in `NOTICE`,
  `THIRD_PARTY_NOTICES.md`, `docs/ATTRIBUTIONS.md`).
- No external image URLs (regression test:
  `tests/test_readme_invariants.py`).
- No stale test count (regression test blocks 51, 129, 199, 234+).

## Where the README could be improved further (not blockers)

- A screenshot of the rendered README could be added to the branding
  audit reports once you capture one in a browser.
- The `About` panel on GitHub was updated on 2026-07-30 to exactly:
  "D-Eye: a FOSS-first, local-first capability and evidence layer for
  AI agents. Local MCP, cited research packets, SSRF-hardened fetch."
  (ASCII-only; zero Unicode dashes). Verified via a read-only
  GitHub API call to `repos/scorpion1476-lgtm/D-Eye`.
- The GitHub social preview PNG is available at
  `assets/branding/derivatives/D-Eye_light.png` (159 KB, well below
  the 1 MB cap) and can be uploaded under Settings > Social preview.
  GitHub does not expose a stable REST endpoint for social-preview
  upload; this remains a browser-Settings-UI action.
