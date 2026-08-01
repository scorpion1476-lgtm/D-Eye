# Dependency and Licence Policy

D-Eye is FOSS-first. The core install and the core test path use only the
Python standard library, so the core has zero runtime dependencies. Any
optional extra (for example the MCP SDK, the remote HTTP transport, or the
browser adapter) must ship under a permissive or weak-copyleft licence on
the allowlist below, and must stay off the mandatory acceptance path.

This policy is enforced automatically by `scripts/scan_licences.py`, which
reads the installed dependency tree and fails if any package carries a
licence outside the allowlist. The test `tests/test_licences.py` runs that
scanner against the installed tree and fails on any denied licence.

## Allowed licences (SPDX)

| Family | Identifiers accepted |
|---|---|
| MIT | MIT, MIT License |
| Apache | Apache-2.0, Apache 2.0, Apache Software License |
| BSD | BSD-2-Clause, BSD-3-Clause, Modified BSD License |
| ISC | ISC, ISC License |
| Python | Python-2.0, PSF-2.0, PSFL, Python Software Foundation License |
| MPL | MPL-2.0, Mozilla Public License 2.0 |
| Public domain | Unlicense |
| LGPL (dynamically linked only) | LGPL-2.1, LGPL-3.0, and the or-later variants |

Multi-licence strings such as "Apache-2.0 OR MIT" are accepted when every
option in the expression is itself on the allowlist.

## Denied licences

The following are rejected outright, because they impose network-copyleft
or commercial restrictions incompatible with a FOSS-first core:

AGPL-3.0 and variants, SSPL, Business Source License (BSL-1.1), the
Elastic License (Elastic-2.0), Commons Clause, and any licence marked
Proprietary, Commercial, or Custom.

## Documented exceptions

`deye` itself, plus the packaging bootstrap tools `pip`, `setuptools`, and
`wheel`, are skipped by the scanner.

## Adding a dependency

1. Confirm the dependency is optional (extras-only) and off by default.
2. Confirm its licence is on the allowlist above.
3. Add it to the relevant extra in `pyproject.toml`.
4. Run `./.venv/bin/python scripts/scan_licences.py` and confirm the
   output shows `denied=0`.
5. If the scanner reports the licence as unknown, add the correct SPDX
   identifier to `ALLOWED_LICENCES` in `scripts/scan_licences.py` and note
   the dependency here.
