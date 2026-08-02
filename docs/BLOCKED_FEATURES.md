# Blocked features (external platform)

D-Eye's catalogue has 167 rows. 153 are PRODUCTION READY (each backed by a real
acceptance test that passes on a clean clone). The 14 rows below are BLOCKED BY
EXTERNAL PLATFORM: they cannot be completed with lawful, keyless, public access
alone, because each depends on a login or anti-bot wall, a hosted account
surface, a vendor API that is not keyless, or a container or hosting runtime the
FOSS clean-clone gate excludes. None is silently dropped; each is listed here
with its precise reason. This list matches the feature audit exactly.

D-Eye never evades a login, CAPTCHA, or anti-bot defence. Where a lawful keyless
portion exists, it is built and tested, and only the gated portion stays blocked.

## Internet and content access (login or anti-bot walls)

- **C03-F004 Twitter/X reading.** The free read-only API tier is deprecated and
  unauthenticated reads are rate-limited or blocked. A lawful read path needs a
  paid X API v2 key, which the FOSS-only core does not require. Registered as a
  lawful-boundary stub; an opt-in adapter could ship if a licensed key is given.
- **C03-F006 YouTube transcripts (live-caption path).** Reliable live captions
  are gated by YouTube's anti-bot CAPTCHA and the legacy timedtext list endpoint
  is deprecated; evading the defence is forbidden and the Data API is not
  keyless. The keyless public portion is built, wired, and tested
  (`tests/test_youtube_transcript.py`); only the gated live path is blocked.
- **C03-F008 LinkedIn access.** LinkedIn's terms prohibit unauthenticated
  scraping and their API requires an approved app plus OAuth. No lawful keyless
  read path.
- **C03-F009 Facebook and Instagram.** Both require Meta Graph API tokens and
  public-page RSS was retired. No lawful keyless read path.
- **C03-F011 Xiaohongshu.** No documented public API exists and scraping would
  breach their terms of service.

## Browser and plugin distribution (per-store review)

- **C04-F004 Browser extensions.** Publishing an extension requires per-store
  review (Chrome Web Store, Firefox Add-ons, Edge Add-ons) under a developer
  account, a platform-side action that cannot be automated. The optional
  Playwright adapter provides equivalent local automation without an installed
  extension.
- **C08-F008 Plugin marketplace.** Marketplace listing and installation can only
  be observed through the Claude client's plugin-marketplace machinery; no
  non-Claude test can prove activation.

## Hosted GitHub account surfaces

- **C09-F001 Private repository publication.** Repository visibility (private) is
  hosted GitHub account state; a local acceptance test cannot observe or set it.
- **C09-F009 Issue and roadmap management.** GitHub Issues and Projects are a
  hosted platform surface; there is no keyless local equivalent to manage them.

## Container and hosting runtimes (excluded from the FOSS gate)

- **C11-F016 Non-root container.** Observing the container runtime UID requires
  building and running the image; the FOSS clean-clone gate has no container
  runtime and the project does not use Docker. The Dockerfile statically
  declares a non-root user.
- **C12-F019 Docker package.** Producing and verifying the image requires
  `docker build`, which the clean-clone gate and the no-Docker constraint
  exclude.
- **C12-F025 Automatic remote hosting.** Observing an automatic remote
  deployment needs a remote host (VPS or cloud) and a container runtime. The
  hostable HTTP MCP server itself (loopback bind, bearer-token auth) is proven
  separately by `tests/test_remote_auth.py`; only the automated remote deploy is
  blocked.

## Hosted Claude account automation

- **C12-F026 Automatic remote connector registration.** Registering a connector
  into a user's Claude account is done by the Claude platform through
  account-scoped APIs and human consent. D-Eye can publish and document a hosted
  MCP endpoint but cannot register a connector into a third party's account; the
  account owner performs that step.
- **C12-F036 Universal activation across every Claude surface.** Each surface
  (Claude web, Projects, Cowork, Desktop, Code, third-party MCP clients) governs
  its own connector or extension registration and requires human opt-in. D-Eye
  ships the local MCP and hosted-HTTP-MCP capabilities each surface consumes but
  cannot silently enable itself; the end user activates it per surface.

## The 14 blocked feature IDs

`C03-F004`, `C03-F006`, `C03-F008`, `C03-F009`, `C03-F011`, `C04-F004`,
`C08-F008`, `C09-F001`, `C09-F009`, `C11-F016`, `C12-F019`, `C12-F025`,
`C12-F026`, `C12-F036`.
