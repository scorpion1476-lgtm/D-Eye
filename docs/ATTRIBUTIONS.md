# D-Eye attributions

This file is the canonical location for third-party attribution notices
required by upstream licences. The user-facing product documentation
(README, guides, CLI help, plugin text) does not name external
reference projects; attribution lives here and in the repo-root files
`NOTICE` and `THIRD_PARTY_NOTICES.md`.

## Structure

- `LICENSE` (repo root): the D-Eye MIT licence.
- `NOTICE` (repo root): concise attribution to studied projects.
- `THIRD_PARTY_NOTICES.md` (repo root): full list of design-pattern
  attributions plus every runtime and tooling dependency.
- `docs/LICENSE_INVENTORY.md`: dependency licences with SPDX
  identifiers, pins, and purpose.
- `docs/FORENSIC_AUDIT_REPORT.md`: historical design-provenance record
  (retained verbatim as an attribution record; the top-of-file banner
  explains its status).
- This file: pointer index so users know where to look.

## Summary of the attribution model

D-Eye is an independent, clean-room implementation. Its architecture
was informed by patterns published in other FOSS projects. No source
file, credential, private API, brand mark, or configuration value
from those projects is bundled inside D-Eye's tracked source.

For the full list of studied projects, their licences, and the
patterns attributed, see [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

## Runtime and tooling dependency attributions

Every dependency D-Eye can install (whether required by core or gated
behind an extras group) is listed with its SPDX licence, pin, purpose,
and replacement path in:

- [`docs/LICENSE_INVENTORY.md`](LICENSE_INVENTORY.md)
- [`docs/DEPENDENCY_AND_LICENCE_POLICY.md`](DEPENDENCY_AND_LICENCE_POLICY.md)

## Verification

- `python3 scripts/scan_licences.py` scans the installed dependency
  tree, resolves each package's licence, and fails on any denied
  licence (AGPL, SSPL, BSL, Elastic, Commons Clause,
  Custom/Proprietary/Commercial).
- `tests/test_licences.py` runs the scan in CI and asserts a clean
  result.
- `sh scripts/run_pip_audit.sh` runs a live OSV vulnerability audit.

## Icon assets

The D-Eye icon assets under `assets/brand/` are the approved D-Eye brand
icons, supplied by the D-Eye project owner and covered by the D-Eye MIT
licence. Their provenance is recorded in
[`assets/brand/MANIFEST.json`](../assets/brand/MANIFEST.json).
