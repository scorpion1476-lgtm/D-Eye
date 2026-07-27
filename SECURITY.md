# Security policy

## Reporting
Report vulnerabilities privately to the maintainers (do not open a public issue).
Include a description, reproduction steps, affected version, and impact.

## Posture
- Read-only by default; write/browser actions require explicit consent.
- Deterministic security decisions (SSRF, redaction, limits) live outside the LLM.
- Retrieved content is always treated as untrusted evidence.
- No credentials are stored inline; only `env:`/`keychain:` references are used.
- A repo-wide secret-scan test (`tests/test_no_secrets_in_repo.py`) blocks releases
  that contain live-token-shaped strings.

## In scope
SSRF, DNS rebinding/TOCTOU, redirect handling, decompression bombs, credential
leakage in logs/exports, prompt-injection labelling, plugin supply-chain safety.

## Known residual risks
See `docs/THREAT_MODEL.md` -- honestly enumerated, including items still on the
roadmap (connector sandboxing, signed bundles, SBOM/SAST in CI).
