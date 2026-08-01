# D-Eye - Test Report

> **Current run (2026-08-01, macOS Darwin 24.6.0, Python 3.14.3):** the full
> suite is **358 passed, 0 failed out of 363 collected** via
> `./.venv/bin/python -m pytest -q -rs`. Four browser tests skip when the
> optional Playwright extra is present, and one live-network test skips
> when its source is unreachable (it passes when reachable), so passing is
> 358 or 359 and skipped is 5 or 4 across runs. Bandit reports 0 high and 0
> medium findings, and the live OSV pip-audit reports no known
> vulnerabilities. The per-phase tables below are historical snapshots;
> their smaller counts (62, 66, 69, 73) are superseded by the current run.

**Date (historical snapshot):** 2026-07-29 · Phase B, superseding the Phase A row below

## Runs executed - Phase B (macOS, Python 3.14.3)

| Environment | Command | Result |
|---|---|---|
| Core (standard library only) | `python -m pytest -q -rs` | **69 passed, 1 skipped** |
| With MCP extras (`mcp[cli]==1.29.0`) | `pip install ".[remote]"` then `pytest -q -rs` | **73 passed, 0 skipped** |
| SAST | `bandit -r deye` | 0 issues (all severities) |
| Dependency audit | `pip-audit` | 0 known vulnerabilities |
| CLI smoke | `deye status` / `deye doctor` | clean JSON; 4/5 connectors usable |

Adds +7 regression tests for the Phase-B security fixes (redaction, decompression bomb, RSS DOCTYPE, router audit).

## Runs executed - Phase A (2026-07-28, branch feature/phase-a-foundation)

| Environment | Command | Result |
|---|---|---|
| Core (standard library only) | `python3 -m pytest -q` | **62 passed, 1 skipped** |
| With MCP extras (isolated venv) | `pytest -q` after `pip install "mcp[cli]" uvicorn starlette` | **66 passed** _(Phase A; superseded by 73 passed, 0 skipped above)_ |
| SAST | `bandit -r deye` | 0 issues (all severities) |
| Live integration | `deye repo psf/requests` | network path OK; GitHub rate-limit handled |

The single skip in the core run is `tests/test_remote_auth.py`, which imports the optional `mcp` package. With the extras installed it runs and passes. The current validated totals are **69 passed / 1 skipped** (core) and **73 passed / 0 skipped** (with MCP extras); the Phase-A "66" and older "51" figures are historical and not the current result.

## New tests added (Phase A)
- `tests/test_graph.py` - polarity + numeric contradiction detection, same-source suppression, export serialisation (5).
- `tests/test_github_connector.py` - slug/URL parsing, envelope build, not-found handling (4).
- `tests/test_exa_adapter.py` - keyless fallback, authenticated request build, answer mode (4).
- `tests/test_rss_guard.py` - DOCTYPE rejection (billion-laughs) + normal-feed parse (2).
