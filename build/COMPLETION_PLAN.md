# D-Eye completion plan (dependency-ordered, honest)

Goal: every one of the 167 catalogue rows is either genuinely PRODUCTION
READY (real capability, reachable through the shipped CLI or MCP surface,
proven by a real acceptance test that passes on a fresh clone) or precisely
justified under criterion (b) (no public interface exists, another OS or
hosted infrastructure is required, or no legitimate public access exists).
No "partial", "mirror", or "implemented but not fully verified" end states.

Honesty rules: promote a row only when a specific real acceptance test
exercises that feature's actual behaviour and passes on a clean clone.
Never promote on a shape-only or hollow test. Never evade an anti-bot or
login defence to make a connector "work"; record such a remainder under (b).

## Baseline (2026-08-01)

Strict reconciled distribution: 55 PRODUCTION READY, 96 IMPLEMENTED BUT NOT
FULLY VERIFIED, 8 PARTIAL, 8 BLOCKED. Full suite green.

Evidence classification of the 112 non-PR rows:
- 67 already cite a genuinely behavioural test file (security core, keyless
  connectors, research and evidence engine, router, MCP tools, lifecycle,
  offline mode). These are promotable once each is mapped to the specific
  real test that is its acceptance and re-verified on a clean clone.
- The remainder rely on shape-only tests (plugin-manifest key checks,
  category-12 mirror source greps, CI-workflow and Dockerfile text checks),
  have no test, or are genuine (b). These need a real acceptance test built,
  a real capability built, or a precise (b) justification.

## Dependency order

1. Security foundation (Cat 11) and capability router (Cat 2): the base
   fetch, policy, redaction, pinning, router. Real E2E tests exist
   (test_policy_ssrf, test_e2e_local_http, test_router,
   test_decompression_guard, test_redact).
2. Connectors (Cat 3): keyless web search, fetch, extract, RSS, GitHub,
   Reddit, V2EX, Xueqiu, Xiaoyuzhou, YouTube metadata and captions.
3. Research and evidence (Cat 5, 6): FTS5 search, extractive answer,
   quality, dedup, evidence store, provenance, evidence graph and
   contradiction detection.
4. MCP surface (Cat 7) and CLI (Cat 12 mirrors resolve to their primaries).
5. Setup and lifecycle (Cat 1), dev workflow (Cat 9), backend (Cat 10).
6. Plugin (Cat 8): structural artefacts; genuine activation needs a real
   Claude client.
7. Browser (Cat 4): optional Playwright extra; live automation needs the
   extra installed.

## Genuine builds required (not just tests)

- C03-F006 YouTube transcripts: DONE as a keyless connector (timedtext plus
  public watch-page player response), wired to CLI and router, real tests.
  Honest remainder under (b): reliable live captions are gated by YouTube's
  anti-bot CAPTCHA (google.com/sorry) on automated hosts and the legacy
  timedtext list endpoint is deprecated; evading the anti-bot defence is
  forbidden, and the credentialed Data API is not keyless. The connector
  degrades cleanly and never evades the challenge.
- C05-F002 Neural search: a keyless local semantic layer (default), with
  heavy neural models only as an optional extra.
- C05-F013 Cost, quota and rate reporting for optional adapters.
- C09-F003 GitHub MCP integration; C09-F007 / C12-F033 signed release and
  bundle verification via a FOSS signing toolchain.

## Criterion (b) candidates (precise justification required per row)

- C03-F004 Twitter/X, C03-F008 LinkedIn, C03-F009 Facebook and Instagram,
  C03-F011 Xiaohongshu: useful data is behind a login wall and active
  anti-bot detection; the build rules forbid circumventing it.
- C03-F006 YouTube transcripts live-caption path: anti-bot gated (above).
- C04-F004 Browser extensions: requires publishing or installing into a
  third-party browser extension store.
- C12-F026 remote connector registration, C12-F036 universal cross-surface
  activation: the hosted Claude vendor exposes no public automation API.
- Cross-OS install proof (Windows) and hosted remote-MCP deployment:
  require another operating system or hosted infrastructure to observe.

## Status of this run

Tranche 1 complete and committed: YouTube transcript connector built,
wired, and tested (real acceptance tests, full suite green). See PROGRESS.md
for the running log. This is a multi-tranche build; subsequent tranches
continue per the order above, promoting only on real, re-verified evidence.
